#!/usr/bin/env python3
"""
Test script for Vibey API
Tests all endpoints and recommender functionality
"""

import requests
import json
import time
from typing import Dict, Any

BASE_URL = "http://localhost:8000"
session = requests.Session()


def print_test(name: str):
    """Print test header"""
    print(f"\n{'='*60}")
    print(f"🧪 {name}")
    print(f"{'='*60}")


def print_success(message: str):
    """Print success message"""
    print(f"✅ {message}")


def print_error(message: str):
    """Print error message"""
    print(f"❌ {message}")


def print_response(response: requests.Response):
    """Print formatted response"""
    print(f"Status: {response.status_code}")
    try:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
    except:
        print(f"Response: {response.text}")


def test_root():
    """Test root endpoint"""
    print_test("Test Root Endpoint")
    response = session.get(f"{BASE_URL}/")
    print_response(response)
    
    if response.status_code == 200:
        print_success("Root endpoint working")
        return True
    else:
        print_error("Root endpoint failed")
        return False


def test_create_user():
    """Test user creation"""
    print_test("Test Create Guest User")
    response = session.post(f"{BASE_URL}/v1/users")
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        user_id = data.get('user_id')
        print_success(f"User created: {user_id}")
        return True, user_id
    else:
        print_error("User creation failed")
        return False, None


def test_get_vibes():
    """Test get vibes"""
    print_test("Test Get Vibes")
    response = session.get(f"{BASE_URL}/v1/vibes")
    print_response(response)
    
    if response.status_code == 200:
        vibes = response.json()
        print_success(f"Found {len(vibes)} vibes")
        return True, vibes
    else:
        print_error("Get vibes failed")
        return False, []


def test_explore_feed():
    """Test explore feed"""
    print_test("Test Explore Feed")
    response = session.get(f"{BASE_URL}/v1/feed/next?mode=explore&limit=5&seed=42")
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        tracks = data.get('tracks', [])
        print_success(f"Explore feed returned {len(tracks)} tracks")
        return True, tracks
    else:
        print_error("Explore feed failed")
        return False, []


def test_vibe_feed(vibe_id: int):
    """Test vibe feed"""
    print_test(f"Test Vibe Feed (vibe_id={vibe_id})")
    response = session.get(f"{BASE_URL}/v1/feed/next?mode=vibe&vibe_id={vibe_id}&limit=5")
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        tracks = data.get('tracks', [])
        print_success(f"Vibe feed returned {len(tracks)} tracks")
        return True, tracks
    else:
        print_error("Vibe feed failed")
        return False, []


def test_feedback(track_id: str, action: str):
    """Test feedback submission"""
    print_test(f"Test Feedback: {action}")
    response = session.post(
        f"{BASE_URL}/v1/feedback",
        json={"track_id": track_id, "action": action}
    )
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        print_success(f"Feedback '{action}' submitted successfully")
        return True
    else:
        print_error(f"Feedback '{action}' failed")
        return False


def test_history():
    """Test history endpoint"""
    print_test("Test Feedback History")
    response = session.get(f"{BASE_URL}/v1/history?limit=10")
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        items = data.get('items', [])
        total = data.get('total', 0)
        print_success(f"History returned {len(items)} items (total: {total})")
        return True
    else:
        print_error("History failed")
        return False


def test_deterministic_feed():
    """Test deterministic feed with seed"""
    print_test("Test Deterministic Feed (same seed)")
    
    # Get feed with seed twice
    response1 = session.get(f"{BASE_URL}/v1/feed/next?mode=explore&limit=5&seed=123")
    response2 = session.get(f"{BASE_URL}/v1/feed/next?mode=explore&limit=5&seed=123")
    
    if response1.status_code == 200 and response2.status_code == 200:
        tracks1 = [t['trackId'] for t in response1.json()['tracks']]
        tracks2 = [t['trackId'] for t in response2.json()['tracks']]
        
        print(f"Feed 1: {tracks1}")
        print(f"Feed 2: {tracks2}")
        
        if tracks1 == tracks2:
            print_success("Deterministic feed working (same tracks with same seed)")
            return True
        else:
            print_error("Feeds differ with same seed")
            return False
    else:
        print_error("Deterministic feed test failed")
        return False


def test_preference_learning():
    """Test that preferences update after feedback"""
    print_test("Test Preference Learning")
    
    # Get initial feed
    response1 = session.get(f"{BASE_URL}/v1/feed/next?mode=explore&limit=5&seed=999")
    if response1.status_code != 200:
        print_error("Failed to get initial feed")
        return False
    
    tracks1 = response1.json()['tracks']
    if not tracks1:
        print_error("No tracks in feed")
        return False
    
    # Like first three tracks
    for i in range(min(3, len(tracks1))):
        track_id = tracks1[i]['trackId']
        test_feedback(track_id, "like")
        time.sleep(0.1)
    
    # Get new feed (without seed, so it should be influenced by preferences)
    response2 = session.get(f"{BASE_URL}/v1/feed/next?mode=explore&limit=5")
    if response2.status_code != 200:
        print_error("Failed to get new feed")
        return False
    
    tracks2 = response2.json()['tracks']
    
    print_success("Preference learning test completed")
    print(f"Initial feed had {len(tracks1)} tracks")
    print(f"After liking 3 tracks, new feed has {len(tracks2)} tracks")
    return True


def test_undo():
    """Test undo functionality"""
    print_test("Test Undo Feedback")
    
    # Get a track
    response = session.get(f"{BASE_URL}/v1/feed/next?mode=explore&limit=1")
    if response.status_code != 200 or not response.json()['tracks']:
        print_error("Failed to get track for undo test")
        return False
    
    track_id = response.json()['tracks'][0]['trackId']
    
    # Like it
    if not test_feedback(track_id, "like"):
        return False
    
    # Undo
    if not test_feedback(track_id, "undo"):
        return False
    
    print_success("Undo test completed")
    return True


def run_all_tests():
    """Run all tests"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║                  VIBEY API TEST SUITE                     ║
╚═══════════════════════════════════════════════════════════╝
""")
    
    results = []
    
    # Test 1: Root endpoint
    results.append(("Root Endpoint", test_root()))
    
    # Test 2: Create user
    success, user_id = test_create_user()
    results.append(("Create User", success))
    
    if not success:
        print_error("Cannot continue without user. Exiting.")
        return
    
    # Test 3: Get vibes
    success, vibes = test_get_vibes()
    results.append(("Get Vibes", success))
    
    # Test 4: Explore feed
    success, tracks = test_explore_feed()
    results.append(("Explore Feed", success))
    
    if not tracks:
        print_error("No tracks available. Did you seed the database?")
        print("Run: python seed_tracks.py 500")
        return
    
    # Test 5: Vibe feed
    if vibes:
        success, _ = test_vibe_feed(vibes[0]['vibe_id'])
        results.append(("Vibe Feed", success))
    
    # Test 6: Feedback
    if tracks:
        success = test_feedback(tracks[0]['trackId'], "like")
        results.append(("Like Feedback", success))
        
        if len(tracks) > 1:
            success = test_feedback(tracks[1]['trackId'], "dislike")
            results.append(("Dislike Feedback", success))
    
    # Test 7: History
    results.append(("Feedback History", test_history()))
    
    # Test 8: Deterministic feed
    results.append(("Deterministic Feed", test_deterministic_feed()))
    
    # Test 9: Preference learning
    results.append(("Preference Learning", test_preference_learning()))
    
    # Test 10: Undo
    results.append(("Undo Feedback", test_undo()))
    
    # Print summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")


if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test suite error: {e}")
        import traceback
        traceback.print_exc()

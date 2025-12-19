# Vibey Backend Deployment Guide

## Local Development

### Prerequisites
- Python 3.11+
- Spotify Developer Account

### Setup

1. **Clone repository**
```bash
cd vibey-backend
```

2. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your Spotify credentials
```

3. **Run setup script**
```bash
chmod +x setup.sh
./setup.sh
```

4. **Start server**
```bash
python main.py
# or
uvicorn main:app --reload
```

5. **Test API**
```bash
python test_api.py
```

Server available at: `http://localhost:8000`

## Docker Deployment

### Build and Run

```bash
# Build image
docker build -t vibey-api .

# Run container
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/.env:/app/.env \
  --name vibey-api \
  vibey-api
```

### Docker Compose

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Production Deployment

### Environment Variables

Required:
```env
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=https://yourdomain.com/v1/auth/spotify/callback
SECRET_KEY=generate_with_secrets.token_urlsafe_32
```

Optional tuning:
```env
EMBEDDING_DIM=128
ALPHA_LIKE=0.3
BETA_DISLIKE=0.5
GAMMA_MORE_LIKE=0.6
VIBE_UNSEEN_RATIO=0.4
```

### Database Migration to PostgreSQL

1. Install psycopg2:
```bash
pip install psycopg2-binary
```

2. Update `.env`:
```env
DATABASE_URL=postgresql://user:pass@localhost:5432/vibey
```

3. Update `database.py` to use SQLAlchemy (recommended) or psycopg2

### Scaling Considerations

#### 1. Use PostgreSQL
SQLite is single-writer. For production:
- PostgreSQL for concurrent writes
- Connection pooling
- Async database driver (asyncpg)

#### 2. Cache Layer
Add Redis for:
- Session storage
- Track metadata caching
- Audio features caching

#### 3. Vector Database
For large catalogs (>1M tracks):
- Pinecone, Qdrant, or Weaviate
- Faster similarity search
- Distributed architecture

#### 4. Background Jobs
Add Celery for:
- Refreshing Spotify tokens
- Batch audio feature fetching
- Analytics processing

#### 5. API Gateway
Use Nginx or Traefik for:
- Rate limiting
- Load balancing
- SSL termination

### Example Production Stack

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  api:
    build: .
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/vibey
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
    restart: always

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=vibey
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - api

volumes:
  postgres_data:
  redis_data:
```

### Security Checklist

- [ ] Change SECRET_KEY from default
- [ ] Use HTTPS in production
- [ ] Enable CORS only for your domains
- [ ] Add rate limiting
- [ ] Sanitize user inputs
- [ ] Use environment variables for secrets
- [ ] Enable database backups
- [ ] Monitor API usage
- [ ] Implement logging
- [ ] Add authentication refresh token rotation

### Monitoring

Recommended tools:
- **Sentry**: Error tracking
- **Prometheus + Grafana**: Metrics
- **ELK Stack**: Log aggregation
- **Uptime Robot**: Availability monitoring

### Performance Tips

1. **Database Indexes**: Already included in schema
2. **Connection Pooling**: Configure database max connections
3. **Response Caching**: Cache vibes, popular tracks
4. **Async I/O**: Use async database drivers
5. **CDN**: Serve artwork URLs through CDN

### Backup Strategy

1. **Database**: Daily automated backups
2. **Audio Features**: Cache in object storage (S3)
3. **User Preferences**: Export to JSON daily
4. **Feedback Logs**: Archive to data warehouse

### Health Checks

Add endpoint:
```python
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "timestamp": int(datetime.now().timestamp()),
        "database": "connected",  # Check db connection
        "spotify": "available"     # Check Spotify API
    }
```

### CI/CD Pipeline

Example GitHub Actions:
```yaml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Build and push Docker image
        run: |
          docker build -t vibey-api .
          docker push yourregistry/vibey-api:latest
      - name: Deploy to server
        run: ssh user@server 'docker-compose pull && docker-compose up -d'
```

## Platform-Specific Guides

### Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Deploy
railway up
```

### Heroku

```bash
# Login
heroku login

# Create app
heroku create vibey-api

# Set config
heroku config:set SPOTIFY_CLIENT_ID=xxx

# Deploy
git push heroku main
```

### AWS EC2

1. Launch Ubuntu instance
2. Install Docker
3. Clone repository
4. Configure `.env`
5. Run with docker-compose
6. Configure security groups (port 8000)
7. Set up Elastic IP
8. Configure Route 53 for DNS

### DigitalOcean

1. Create Droplet (Ubuntu)
2. Use App Platform for managed deployment
3. Connect GitHub repository
4. Configure environment variables
5. Deploy

## Troubleshooting

### Database locked error
SQLite issue with concurrent writes. Migrate to PostgreSQL.

### Spotify token expired
Implement background job to refresh tokens:
```python
from apscheduler.schedulers.background import BackgroundScheduler

def refresh_tokens():
    # Refresh expired Spotify tokens
    pass

scheduler = BackgroundScheduler()
scheduler.add_job(refresh_tokens, 'interval', hours=1)
scheduler.start()
```

### Memory usage high
- Reduce embedding dimension
- Implement pagination for history
- Use database cursor instead of loading all tracks

### Slow feed generation
- Add caching layer
- Pre-compute candidate pools
- Use vector database for similarity search

## Support

For issues:
1. Check logs: `docker-compose logs -f`
2. Test API: `python test_api.py`
3. Verify database: `sqlite3 vibey.db .tables`
4. Check Spotify credentials

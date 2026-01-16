# Deployment Guide - Token Generation Service

## Production Deployment Checklist

### Pre-Deployment

- [ ] **Google Cloud Setup**
  - [ ] Create OAuth 2.0 credentials
  - [ ] Configure authorized redirect URIs
  - [ ] Note down Client ID and Client Secret
  - [ ] Enable Google Business Profile API

- [ ] **Infrastructure**
  - [ ] PostgreSQL database provisioned
  - [ ] Database connection tested
  - [ ] Docker/Container runtime installed
  - [ ] SSL certificates ready (for HTTPS)

- [ ] **Configuration**
  - [ ] Environment variables configured
  - [ ] Strong SECRET_KEY generated
  - [ ] Database credentials secured
  - [ ] CORS origins configured

### Deployment Steps

#### 1. Environment Configuration

Create `.env` file:

```bash
# Application
ENVIRONMENT=production
DEBUG=false
APP_NAME=Token Generation Service
APP_VERSION=1.0.0

# Server
HOST=0.0.0.0
PORT=8002
WORKERS=4

# Database
DATABASE_URL=postgresql://token_user:STRONG_PASSWORD@db-host:5432/token_service_db
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40

# Google OAuth
GOOGLE_AUTH_URL=https://accounts.google.com/o/oauth2/v2/auth
GOOGLE_TOKEN_URL=https://oauth2.googleapis.com/token
GOOGLE_SCOPE=https://www.googleapis.com/auth/business.manage

# Token Configuration
TOKEN_EXPIRY_BUFFER=300
DEFAULT_REDIRECT_URI=https://your-domain.com/auth/callback

# Security
SECRET_KEY=$(openssl rand -hex 32)
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# CORS (specify allowed origins)
ALLOWED_ORIGINS=["https://your-frontend.com", "https://your-api.com"]

# Logging
LOG_LEVEL=INFO
```

#### 2. Database Setup

```bash
# Connect to PostgreSQL
psql -h your-db-host -U postgres

# Create database and user
CREATE DATABASE token_service_db;
CREATE USER token_user WITH ENCRYPTED PASSWORD 'STRONG_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE token_service_db TO token_user;
\q
```

#### 3. Build Docker Image

```bash
# Build image
docker build -t token-generation-service:1.0.0 .

# Tag for registry
docker tag token-generation-service:1.0.0 your-registry/token-generation-service:1.0.0

# Push to registry
docker push your-registry/token-generation-service:1.0.0
```

#### 4. Deploy Container

**Option A: Docker Run**

```bash
docker run -d \
  --name token-generation-service \
  --restart unless-stopped \
  -p 8002:8002 \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  your-registry/token-generation-service:1.0.0
```

**Option B: Docker Compose**

```yaml
version: '3.8'

services:
  token-service:
    image: your-registry/token-generation-service:1.0.0
    container_name: token-generation-service
    restart: unless-stopped
    ports:
      - "8002:8002"
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=${DATABASE_URL}
      - SECRET_KEY=${SECRET_KEY}
      - LOG_LEVEL=INFO
    volumes:
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:8002/health', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

Deploy:
```bash
docker-compose up -d
```

#### 5. Run Database Migrations

```bash
# Inside container
docker exec -it token-generation-service alembic upgrade head

# Or during startup (already in docker-compose.yml)
```

#### 6. Verify Deployment

```bash
# Health check
curl https://your-domain.com/health

# Expected response
{
  "status": "healthy",
  "service": "Token Generation Service",
  "version": "1.0.0",
  "timestamp": "2026-01-16T10:00:00",
  "database": "connected"
}
```

### Kubernetes Deployment

#### ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: token-service-config
data:
  ENVIRONMENT: "production"
  PORT: "8002"
  LOG_LEVEL: "INFO"
  GOOGLE_AUTH_URL: "https://accounts.google.com/o/oauth2/v2/auth"
  GOOGLE_TOKEN_URL: "https://oauth2.googleapis.com/token"
  GOOGLE_SCOPE: "https://www.googleapis.com/auth/business.manage"
```

#### Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: token-service-secret
type: Opaque
stringData:
  DATABASE_URL: "postgresql://token_user:password@postgres:5432/token_service_db"
  SECRET_KEY: "your-secret-key-here"
```

#### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: token-generation-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: token-service
  template:
    metadata:
      labels:
        app: token-service
    spec:
      containers:
      - name: token-service
        image: your-registry/token-generation-service:1.0.0
        ports:
        - containerPort: 8002
        envFrom:
        - configMapRef:
            name: token-service-config
        - secretRef:
            name: token-service-secret
        livenessProbe:
          httpGet:
            path: /health
            port: 8002
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8002
          initialDelaySeconds: 10
          periodSeconds: 5
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

#### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: token-service
spec:
  selector:
    app: token-service
  ports:
  - port: 8002
    targetPort: 8002
  type: ClusterIP
```

#### Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: token-service-ingress
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - token-service.your-domain.com
    secretName: token-service-tls
  rules:
  - host: token-service.your-domain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: token-service
            port:
              number: 8002
```

Deploy:
```bash
kubectl apply -f k8s/
```

### Post-Deployment

#### 1. Register Initial Client

```bash
curl -X POST https://your-domain.com/clients \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "YOUR_GOOGLE_CLIENT_ID",
    "client_secret": "YOUR_GOOGLE_CLIENT_SECRET",
    "redirect_uri": "https://your-domain.com/auth/callback"
  }'
```

#### 2. Complete OAuth Flow

Navigate to: `https://your-domain.com/oauth/login/{client_id}`

#### 3. Test Token Validation

```bash
curl https://your-domain.com/tokens/validate/{client_id}
```

### Monitoring

#### Logs

```bash
# Docker
docker logs -f token-generation-service

# Kubernetes
kubectl logs -f deployment/token-generation-service
```

#### Metrics to Monitor

- **Health endpoint response time**
- **Database connection pool usage**
- **Token refresh success/failure rate**
- **OAuth flow completion rate**
- **API response times**

#### Set Up Alerts

- Service unhealthy for > 2 minutes
- Database connection failures
- Token refresh failures > 10% in 5 minutes
- High memory/CPU usage

### Backup & Recovery

#### Database Backup

```bash
# Backup
pg_dump -h db-host -U token_user token_service_db > backup.sql

# Restore
psql -h db-host -U token_user token_service_db < backup.sql
```

#### Automated Backup (Daily)

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
DB_HOST="your-db-host"
DB_NAME="token_service_db"
DB_USER="token_user"

pg_dump -h $DB_HOST -U $DB_USER $DB_NAME | gzip > $BACKUP_DIR/backup_$DATE.sql.gz

# Keep only last 30 days
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete
```

Add to cron:
```bash
0 2 * * * /path/to/backup.sh
```

### Scaling

#### Horizontal Scaling

```bash
# Docker Compose
docker-compose up -d --scale token-service=3

# Kubernetes
kubectl scale deployment token-generation-service --replicas=5
```

#### Load Balancing

Use nginx or cloud load balancer:

```nginx
upstream token_service {
    server token-service-1:8002;
    server token-service-2:8002;
    server token-service-3:8002;
}

server {
    listen 80;
    server_name token-service.your-domain.com;

    location / {
        proxy_pass http://token_service;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Security Hardening

- [ ] Use HTTPS everywhere (TLS 1.2+)
- [ ] Implement rate limiting
- [ ] Set up firewall rules
- [ ] Use secrets management (Vault, AWS Secrets Manager)
- [ ] Enable database SSL connections
- [ ] Implement API authentication for admin endpoints
- [ ] Regular security updates
- [ ] Audit logs for sensitive operations

### Rollback Procedure

```bash
# Docker
docker stop token-generation-service
docker run -d --name token-generation-service \
  your-registry/token-generation-service:1.0.0-previous

# Kubernetes
kubectl rollout undo deployment/token-generation-service
```

### Troubleshooting

**Service won't start**
- Check logs: `docker logs token-generation-service`
- Verify database connection
- Check environment variables

**Database connection timeout**
- Check PostgreSQL is running
- Verify credentials
- Check firewall rules

**OAuth callback fails**
- Verify redirect URI matches Google Console
- Check state parameter validation
- Review logs for specific error

**Token refresh failing**
- Check Google API quota
- Verify refresh token exists
- Check client credentials

### Performance Tuning

#### Database

```python
# config.py adjustments
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=60
```

#### Uvicorn Workers

```bash
# For production
uvicorn src.token_service.api.main:app \
  --host 0.0.0.0 \
  --port 8002 \
  --workers 8 \
  --worker-class uvicorn.workers.UvicornWorker
```

Or use Gunicorn:
```bash
gunicorn src.token_service.api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8002
```

### Maintenance

#### Database Cleanup

```sql
-- Remove expired OAuth states (monthly)
DELETE FROM oauth_states 
WHERE expires_at < NOW() - INTERVAL '30 days';

-- Cleanup old invalid tokens (monthly)
DELETE FROM tokens 
WHERE is_valid = false 
AND updated_at < NOW() - INTERVAL '90 days';
```

#### Update Service

```bash
# Pull new image
docker pull your-registry/token-generation-service:1.1.0

# Stop old version
docker stop token-generation-service

# Start new version
docker run -d --name token-generation-service \
  your-registry/token-generation-service:1.1.0

# Run migrations
docker exec token-generation-service alembic upgrade head
```

---

## Support & Documentation

- **API Docs**: https://your-domain.com/docs
- **Health Check**: https://your-domain.com/health
- **Repository**: Link to your Git repository
- **Support**: support@your-company.com

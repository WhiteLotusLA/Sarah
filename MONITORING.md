# Sarah AI Monitoring Setup

This document describes the monitoring infrastructure for Sarah AI using Prometheus and Grafana.

## Overview

The monitoring stack consists of:
- **Prometheus**: Time-series database for metrics collection
- **Grafana**: Visualization and dashboarding
- **Alertmanager**: Alert routing and management
- **Various Exporters**: For collecting metrics from different components

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Sarah API  │────▶│  Prometheus  │────▶│   Grafana   │
└─────────────┘     └──────────────┘     └─────────────┘
       │                    │                     │
       │                    ▼                     │
       │            ┌──────────────┐              │
       │            │ Alertmanager │              │
       │            └──────────────┘              │
       │                                          │
       ▼                                          ▼
┌─────────────┐                          ┌─────────────┐
│   Metrics   │                          │ Dashboards  │
│  Endpoint   │                          │   & Alerts  │
└─────────────┘                          └─────────────┘
```

## Quick Start

1. **Start the monitoring stack:**
   ```bash
   docker-compose -f docker-compose.monitoring.yml up -d
   ```

2. **Access the services:**
   - Prometheus: http://localhost:9090
   - Grafana: http://localhost:3000 (default: admin/admin)
   - Alertmanager: http://localhost:9093

3. **Verify metrics collection:**
   - Navigate to Prometheus targets: http://localhost:9090/targets
   - All targets should show as "UP"

## Metrics Collection

### Application Metrics

The Sarah API exposes metrics at `/metrics` endpoint, including:

- **HTTP Metrics:**
  - `http_requests_total`: Total HTTP requests by method, endpoint, and status
  - `http_request_duration_seconds`: Request latency histogram
  - `http_requests_in_progress`: Currently processing requests

- **WebSocket Metrics:**
  - `websocket_connections`: Active WebSocket connections by endpoint
  - `websocket_messages_total`: Total messages sent/received

- **Agent Metrics:**
  - `sarah_agent_up`: Agent availability (1=up, 0=down)
  - `sarah_agent_memory_mb`: Agent memory usage
  - `sarah_agent_tasks_total`: Tasks processed by agents
  - `sarah_agent_response_time_seconds`: Agent response times

- **System Metrics:**
  - `sarah_memory_operations_total`: Memory system operations
  - `sarah_rate_limit_exceeded_total`: Rate limit violations
  - `sarah_backup_last_success_timestamp`: Last successful backup time

### Infrastructure Metrics

Additional exporters collect:
- **Node Exporter**: System metrics (CPU, memory, disk, network)
- **PostgreSQL Exporter**: Database metrics
- **Redis Exporter**: Cache metrics
- **cAdvisor**: Container metrics

## Dashboards

### Sarah AI Overview Dashboard

The main dashboard provides:
- API health status
- Request rate and latency
- Agent status and performance
- Resource utilization
- WebSocket connections
- Error rates

Access at: http://localhost:3000/d/sarah-overview/sarah-ai-overview

## Alerting

### Alert Rules

Configured alerts include:

**Critical Alerts:**
- API down for >2 minutes
- PostgreSQL or Redis down
- No successful backup in 24 hours

**Warning Alerts:**
- High API latency (>1s for 5min)
- High error rate (>5% for 5min)
- High resource usage (CPU/Memory >85%)
- Agent down or high memory usage

### Alert Routing

Alerts are routed through Alertmanager:
1. All alerts sent to Sarah API webhook
2. Critical alerts can be configured for email/SMS/Slack
3. Alerts are grouped and deduplicated

## Custom Metrics Integration

To add custom metrics in your code:

```python
from sarah.api.metrics import (
    track_agent_metrics,
    track_memory_operation,
    update_agent_health
)

# Track agent operations
@track_agent_metrics("my_agent", "custom")
async def process_task():
    # Your code here
    pass

# Track memory operations
track_memory_operation("store", "success")

# Update agent health
update_agent_health("my_agent", "custom", is_up=True)
```

## Configuration

### Prometheus Configuration

Edit `monitoring/prometheus/prometheus.yml` to:
- Add new scrape targets
- Adjust scrape intervals
- Configure service discovery

### Grafana Configuration

- Dashboards: `monitoring/grafana/dashboards/`
- Datasources: `monitoring/grafana/provisioning/datasources/`
- Settings: `monitoring/grafana/grafana.ini`

### Alert Configuration

- Alert rules: `monitoring/prometheus/rules/alerts.yml`
- Alertmanager: `monitoring/alerting/alertmanager.yml`

## Troubleshooting

### Metrics Not Appearing

1. Check Prometheus targets: http://localhost:9090/targets
2. Verify the application is exposing metrics: http://localhost:8000/metrics
3. Check Docker network connectivity

### High Memory Usage

1. Adjust Prometheus retention: `--storage.tsdb.retention.time=7d`
2. Reduce scrape frequency in prometheus.yml
3. Limit Grafana dashboard refresh rates

### Alert Not Firing

1. Check alert rules in Prometheus: http://localhost:9090/alerts
2. Verify Alertmanager is receiving alerts: http://localhost:9093
3. Check webhook endpoints are accessible

## Best Practices

1. **Metric Naming**: Follow Prometheus naming conventions
2. **Label Cardinality**: Avoid high-cardinality labels
3. **Dashboard Design**: Keep dashboards focused and fast
4. **Alert Fatigue**: Set appropriate thresholds to avoid noise
5. **Retention Policy**: Balance storage vs. historical data needs

## Scaling Considerations

For production deployments:
1. Use remote storage for Prometheus (e.g., Thanos, Cortex)
2. Deploy Grafana in HA mode with shared database
3. Implement metric aggregation for high-volume data
4. Use federation for multi-region deployments

## Security

1. Enable authentication for all services
2. Use TLS for metric endpoints
3. Restrict network access to monitoring services
4. Implement RBAC in Grafana
5. Encrypt sensitive data in alerts
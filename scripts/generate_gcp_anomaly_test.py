import json
import random
from datetime import datetime, timedelta
import numpy as np
import os

def generate_gcp_test_logs():
    """Generate 1000 realistic GCP logs with embedded anomaly patterns."""
    logs = []
    base_time = datetime.utcnow() - timedelta(minutes=30)
    
    print("Generating GCP test logs with anomaly patterns...")
    
    # Normal baseline (first 600 logs)
    print("📊 Generating baseline logs (1-600)...")
    for i in range(600):
        timestamp = base_time + timedelta(seconds=i*2)
        latency = np.random.normal(200, 50)  # Normal: 200ms ± 50ms
        
        log = {
            "insertId": f"log{i:04d}",
            "timestamp": timestamp.isoformat() + "Z",
            "severity": "INFO",
            "resource": {
                "type": "cloudsql_database",
                "labels": {
                    "database_id": "prod-db-1",
                    "region": "us-central1"
                }
            },
            "jsonPayload": {
                "latency_ms": max(50, int(latency)),
                "query": "SELECT * FROM users WHERE id = ?",
                "rows_examined": random.randint(1, 100),
                "connection_id": random.randint(1, 50)
            },
            "httpRequest": {
                "status": 200,
                "latency": f"{latency/1000:.3f}s",
                "requestMethod": "POST",
                "requestUrl": "/api/users/query"
            },
            "textPayload": f"Query executed successfully in {int(latency)}ms"
        }
        logs.append(log)
    
    # ANOMALY 1: Latency spike pattern (logs 600-700)
    # Simulating deployment at 15:42 causing gradual degradation
    print("🚨 Generating ANOMALY 1: Latency spike pattern (600-700)...")
    deployment_time = base_time + timedelta(seconds=1200)
    for i in range(600, 700):
        timestamp = deployment_time + timedelta(seconds=(i-600)*2)
        # Latency increases progressively after deployment
        latency = 2000 + (i-600) * 30 + random.randint(-200, 200)  # Starting at 2s, getting worse
        
        log = {
            "insertId": f"log{i:04d}",
            "timestamp": timestamp.isoformat() + "Z",
            "severity": "WARNING" if latency < 5000 else "ERROR",
            "resource": {
                "type": "cloudsql_database",
                "labels": {
                    "database_id": "prod-db-1",
                    "region": "us-central1"
                }
            },
            "jsonPayload": {
                "latency_ms": int(latency),
                "query": "SELECT * FROM orders JOIN users ON users.id = orders.user_id WHERE orders.created_at > ?",
                "rows_examined": random.randint(10000, 50000),
                "deployment_id": "v2.3.1",  # Correlation hint
                "connection_id": random.randint(1, 50),
                "slow_query_reason": "Missing index on orders.created_at"
            },
            "httpRequest": {
                "status": 200 if random.random() > 0.3 else 504,  # 30% timeouts
                "latency": f"{latency/1000:.3f}s",
                "requestMethod": "POST",
                "requestUrl": "/api/orders/search"
            },
            "labels": {
                "deployment": "v2.3.1",
                "deployment_time": "15:42:00",
                "performance_issue": "true"
            }
        }
        
        if latency > 5000:
            log["severity"] = "ERROR"
            log["textPayload"] = f"Query timeout after {int(latency)}ms - possible deployment issue"
            
        logs.append(log)
    
    # ANOMALY 2: Authentication failure burst (logs 700-750)
    # Simulating potential security issue/brute force attack
    print("🚨 Generating ANOMALY 2: Authentication failure burst (700-750)...")
    auth_burst_time = base_time + timedelta(seconds=1400)
    suspicious_ips = [f"192.168.1.{random.randint(100, 110)}" for _ in range(5)]
    
    for i in range(700, 750):
        timestamp = auth_burst_time + timedelta(seconds=(i-700)*0.5)  # Rapid succession
        source_ip = random.choice(suspicious_ips)
        
        log = {
            "insertId": f"log{i:04d}",
            "timestamp": timestamp.isoformat() + "Z",
            "severity": "ERROR",
            "resource": {
                "type": "cloudsql_database",
                "labels": {
                    "database_id": "prod-db-1",
                    "region": "us-central1"
                }
            },
            "textPayload": f"Authentication failed for user 'admin' from {source_ip}",
            "jsonPayload": {
                "error_code": "INVALID_PASSWORD",
                "source_ip": source_ip,
                "user": "admin",
                "attempts_count": i - 699,
                "user_agent": "curl/7.68.0",
                "auth_method": "password"
            },
            "httpRequest": {
                "status": 401,
                "latency": "0.050s",
                "requestMethod": "POST",
                "requestUrl": "/auth/login",
                "remoteIp": source_ip
            },
            "labels": {
                "security": "auth_failure",
                "attack_type": "brute_force"
            }
        }
        logs.append(log)
    
    # ANOMALY 3: Cascading failures (logs 750-850)
    # Connection pool exhaustion leading to various errors
    print("🚨 Generating ANOMALY 3: Cascading connection failures (750-850)...")
    cascade_time = base_time + timedelta(seconds=1500)
    error_messages = [
        "Connection pool exhausted",
        "Unable to acquire connection within 30s", 
        "Too many connections",
        "Connection refused by server",
        "Database server has gone away",
        "Lost connection to database server during query"
    ]
    
    for i in range(750, 850):
        timestamp = cascade_time + timedelta(seconds=(i-750)*2)
        error_type = random.choice(error_messages)
        active_connections = min(600, 450 + (i-750) * 2)  # Increasing to max
        
        log = {
            "insertId": f"log{i:04d}",
            "timestamp": timestamp.isoformat() + "Z",
            "severity": "ERROR" if active_connections > 550 else "WARNING",
            "resource": {
                "type": "cloudsql_database",
                "labels": {
                    "database_id": "prod-db-1",
                    "region": "us-central1"
                }
            },
            "textPayload": f"Database error: {error_type}",
            "jsonPayload": {
                "error_code": "CONNECTION_ERROR",
                "active_connections": active_connections,
                "max_connections": 600,
                "queue_size": max(0, (i-750) * 2),
                "connection_wait_time_ms": min(30000, (i-750) * 100),
                "error_type": error_type.lower().replace(" ", "_")
            },
            "httpRequest": {
                "status": 503 if active_connections > 580 else 500,
                "latency": "30.000s" if active_connections > 580 else f"{random.uniform(5, 15):.3f}s",
                "requestMethod": "POST",
                "requestUrl": "/api/database/query"
            },
            "labels": {
                "issue_type": "connection_pool_exhaustion",
                "cascading_failure": "true"
            }
        }
        logs.append(log)
    
    # Normal recovery logs with occasional warnings (logs 850-1000)
    print("📊 Generating recovery period logs (850-1000)...")
    for i in range(850, 1000):
        timestamp = base_time + timedelta(seconds=1700 + (i-850)*2)
        latency = np.random.normal(250, 75)  # Slightly elevated but recovering
        severity = "INFO" if random.random() > 0.1 else "WARNING"
        status = 200 if random.random() > 0.05 else (500 if random.random() > 0.7 else 503)
        
        log = {
            "insertId": f"log{i:04d}",
            "timestamp": timestamp.isoformat() + "Z",
            "severity": severity,
            "resource": {
                "type": "cloudsql_database",
                "labels": {
                    "database_id": "prod-db-1",
                    "region": "us-central1"
                }
            },
            "jsonPayload": {
                "latency_ms": max(50, int(latency)),
                "query": "SELECT * FROM products WHERE category = ? AND status = 'active'",
                "rows_examined": random.randint(1, 1000),
                "connection_id": random.randint(1, 50)
            },
            "httpRequest": {
                "status": status,
                "latency": f"{latency/1000:.3f}s",
                "requestMethod": "GET",
                "requestUrl": "/api/products/search"
            },
            "textPayload": f"Product search completed in {int(latency)}ms"
        }
        
        if status != 200:
            log["textPayload"] = f"Product search failed with status {status}"
            log["severity"] = "ERROR" if status >= 500 else "WARNING"
            
        logs.append(log)
    
    return logs

def save_logs_to_file(logs, filename):
    """Save logs to JSON file with proper formatting."""
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    with open(filename, 'w') as f:
        # Save as JSONL format (one JSON object per line) for easier parsing
        for log in logs:
            json.dump(log, f, separators=(',', ':'))
            f.write('\n')

def main():
    print("🏗️  Generating GCP Anomaly Detection Test Data")
    print("=" * 50)
    
    # Generate test logs
    logs = generate_gcp_test_logs()
    
    # Save to file
    output_file = 'examples/gcp_1000_logs_with_anomalies.json'
    save_logs_to_file(logs, output_file)
    
    print(f"\n✅ Generated {len(logs)} logs saved to: {output_file}")
    print("\n📋 Anomaly Patterns Embedded:")
    print("   🔸 Logs 1-600:    Normal baseline (200ms avg latency)")
    print("   🚨 Logs 600-700:  Latency spike pattern (deployment correlation)")
    print("   🚨 Logs 700-750:  Authentication failure burst (security pattern)")
    print("   🚨 Logs 750-850:  Cascading connection failures")
    print("   🔸 Logs 850-1000: Recovery period with occasional issues")
    
    print("\n🎯 Expected Detections:")
    print("   ✓ Progressive latency degradation after deployment")
    print("   ✓ Brute force authentication attack pattern")
    print("   ✓ Connection pool exhaustion cascade")
    print("   ✓ Temporal correlations with deployment events")
    print("   ✓ Resource-specific patterns")
    
    # Generate summary statistics
    severities = {}
    resources = {}
    for log in logs:
        sev = log.get('severity', 'UNKNOWN')
        severities[sev] = severities.get(sev, 0) + 1
        
        res_type = log.get('resource', {}).get('type', 'unknown')
        resources[res_type] = resources.get(res_type, 0) + 1
    
    print(f"\n📊 Log Distribution:")
    for severity, count in sorted(severities.items()):
        print(f"   {severity}: {count} logs")
    
    print(f"\n🏷️  Resource Types:")
    for resource, count in sorted(resources.items()):
        print(f"   {resource}: {count} logs")

if __name__ == "__main__":
    main() 
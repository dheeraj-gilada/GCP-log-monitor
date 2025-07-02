#!/usr/bin/env python3
"""
Test script to demonstrate the AI supervisor integration with the monitoring engine.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from app.services.monitoring_supervisor import MonitoringSupervisor, MonitoringContext
from app.services.anomaly_detection import DetectionThresholds
from app.models.schemas import LogEntry, LogSeverity, LogResource, ResourceType, Anomaly, AnomalyType, AnomalySeverity, DetectionMethod


def create_test_logs() -> List[LogEntry]:
    """Create test log entries with various error patterns."""
    base_time = datetime.now(timezone.utc)
    logs = []
    
    # Normal logs
    for i in range(80):
        logs.append(LogEntry(
            id=f"log_{i}",
            timestamp=base_time - timedelta(minutes=i//8),
            message=f"Processing request {i} successfully",
            severity=LogSeverity.INFO,
            resource=LogResource(
                type=ResourceType.GCE_INSTANCE,
                labels={"name": f"instance-{i%5}", "zone": "us-central1-a"}
            )
        ))
    
    # Error logs to trigger anomalies
    for i in range(20):
        logs.append(LogEntry(
            id=f"error_log_{i}",
            timestamp=base_time - timedelta(minutes=i//4),
            message=f"Database connection failed: Connection timeout after 30s",
            severity=LogSeverity.ERROR,
            resource=LogResource(
                type=ResourceType.CLOUDSQL_DATABASE,
                labels={"name": f"db-instance-{i%2}", "zone": "us-central1-a"}
            )
        ))
    
    return logs


def create_test_anomalies() -> List[Anomaly]:
    """Create test anomalies for supervisor analysis."""
    return [
        Anomaly(
            id="anomaly_1",
            type=AnomalyType.HIGH_ERROR_RATE,
            severity=AnomalySeverity.MEDIUM,
            title="High Error Rate Detected",
            description="Error rate spike detected: 20% error rate in last 10 minutes",
            confidence=0.85,
            affected_resources=["db-instance-0", "db-instance-1"],
            detection_method=DetectionMethod.STATISTICAL,
            timestamp=datetime.now(timezone.utc),
            affected_logs_count=20,
            resource_type=ResourceType.CLOUDSQL_DATABASE,
            time_window_minutes=10
        ),
        Anomaly(
            id="anomaly_2", 
            type=AnomalyType.REPEATED_ERRORS,
            severity=AnomalySeverity.HIGH,
            title="Repeated Errors Detected",
            description="Repeated database connection timeouts detected",
            confidence=0.92,
            affected_resources=["db-instance-0", "db-instance-1"],
            detection_method=DetectionMethod.PATTERN,
            timestamp=datetime.now(timezone.utc),
            affected_logs_count=15,
            resource_type=ResourceType.CLOUDSQL_DATABASE,
            time_window_minutes=10
        )
    ]


async def test_supervisor_analysis():
    """Test the supervisor's analysis capabilities."""
    print("🤖 Testing AI Supervisor Integration")
    print("=" * 50)
    
    # Initialize supervisor
    supervisor = MonitoringSupervisor()
    
    if not supervisor.is_supervisor_available():
        print("❌ Supervisor not available - missing OpenAI API key or SDK")
        return
    
    print(f"✅ Supervisor initialized: {supervisor.is_supervisor_available()}")
    
    # Create test data
    logs = create_test_logs()
    anomalies = create_test_anomalies()
    
    print(f"📊 Test data created:")
    print(f"   - Logs: {len(logs)} entries")
    print(f"   - Anomalies: {len(anomalies)} detected")
    
    # Create monitoring context
    error_logs = [log for log in logs if log.severity in [LogSeverity.ERROR, LogSeverity.CRITICAL]]
    error_rate = len(error_logs) / len(logs)
    
    context = MonitoringContext(
        total_logs=len(logs),
        window_minutes=10,
        error_rate=error_rate,
        anomaly_count=len(anomalies),
        previous_anomalies=[]
    )
    
    print(f"📈 Monitoring context:")
    print(f"   - Error rate: {error_rate:.1%}")
    print(f"   - Window: {context.window_minutes} minutes")
    print(f"   - Total logs: {context.total_logs}")
    
    # Create detection thresholds
    thresholds = DetectionThresholds(
        error_rate_threshold=0.05,  # 5%
        volume_spike_multiplier=3.0,
        latency_threshold_ms=5000
    )
    
    print(f"🎯 Current thresholds:")
    print(f"   - Error rate: {thresholds.error_rate_threshold:.1%}")
    print(f"   - Volume multiplier: {thresholds.volume_spike_multiplier}x")
    print(f"   - Latency: {thresholds.latency_threshold_ms}ms")
    
    print("\n🔍 Running supervisor analysis...")
    
    try:
        # Run supervisor analysis
        decision = await supervisor.analyze_monitoring_situation(
            anomalies, logs, context, thresholds
        )
        
        if decision:
            print(f"\n✅ Supervisor Analysis Complete!")
            print("=" * 50)
            
            print(f"🧠 Reasoning:")
            print(f"   {decision.reasoning}")
            
            print(f"\n📊 Decision Details:")
            print(f"   - Confidence: {decision.confidence:.1%}")
            print(f"   - Severity adjustment: {decision.severity_adjustment or 'None'}")
            print(f"   - Escalate to human: {decision.escalate_to_human}")
            
            if decision.threshold_adjustments:
                print(f"\n🎯 Threshold Adjustments:")
                for key, value in decision.threshold_adjustments.items():
                    print(f"   - {key}: {value}")
            
            if decision.suggested_actions:
                print(f"\n🔧 Suggested Actions:")
                for i, action in enumerate(decision.suggested_actions[:5], 1):
                    print(f"   {i}. {action}")
                if len(decision.suggested_actions) > 5:
                    print(f"   ... and {len(decision.suggested_actions) - 5} more")
            
            if decision.incident_summary:
                print(f"\n📋 Incident Summary:")
                print(f"   {decision.incident_summary[:200]}...")
        
        else:
            print("❌ No decision returned from supervisor")
    
    except Exception as e:
        print(f"❌ Supervisor analysis failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test decision history
    history = supervisor.get_decision_history(3)
    print(f"\n📚 Decision History: {len(history)} entries")
    
    print("\n✅ Supervisor test completed!")


async def test_monitoring_engine_integration():
    """Test the supervisor integration with the monitoring engine."""
    print("\n🏭 Testing Monitoring Engine Integration")
    print("=" * 50)
    
    from app.core.monitoring_engine import MonitoringEngine
    
    engine = MonitoringEngine()
    
    print(f"✅ Engine initialized")
    print(f"🤖 Supervisor enabled: {engine.config.enable_ai_supervisor}")
    print(f"🔗 Supervisor available: {engine.supervisor.is_supervisor_available() if engine.supervisor else False}")
    
    # Test supervisor status
    status = engine.get_supervisor_status()
    print(f"\n📊 Supervisor Status:")
    for key, value in status.items():
        if key == "capabilities":
            print(f"   - {key}: {len(value)} capabilities")
        else:
            print(f"   - {key}: {value}")
    
    # Test decision history
    history = engine.get_supervisor_decision_history(5)
    print(f"\n📚 Decision History: {len(history)} entries")
    
    print("✅ Engine integration test completed!")


async def main():
    """Main test function."""
    print("🚀 AI Supervisor Integration Test")
    print("=" * 80)
    
    await test_supervisor_analysis()
    await test_monitoring_engine_integration()
    
    print("\n🎉 All tests completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main()) 
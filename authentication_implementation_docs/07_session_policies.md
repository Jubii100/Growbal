# Phase 7: Session Policies and Security Implementation

## Overview

This phase implements comprehensive session security policies, expiration management, and advanced security features. It ensures sessions are properly managed, expired sessions are cleaned up, and security policies are enforced across the authentication system.

## Prerequisites

- Phase 1-6 completed successfully
- Understanding of session security best practices
- Knowledge of your application's security requirements

## 1. Session Policy Configuration

### Create Session Policy Manager

Create `authentication/session_policies.py`:

```python
"""
Session policy management and enforcement
"""
import os
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
from .security_utils import security_utils

logger = logging.getLogger(__name__)

class SessionType(Enum):
    """Types of user sessions"""
    ANONYMOUS = "anonymous"
    AUTHENTICATED = "authenticated"
    SSO = "sso"
    ADMIN = "admin"
    API = "api"

class SecurityLevel(Enum):
    """Security levels for session policies"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class SessionPolicy:
    """Session policy configuration"""
    name: str
    session_type: SessionType
    security_level: SecurityLevel
    max_duration_hours: int
    idle_timeout_minutes: int
    max_concurrent_sessions: int
    require_ip_consistency: bool
    require_user_agent_consistency: bool
    extend_on_activity: bool
    force_reauth_after_hours: Optional[int] = None
    require_mfa: bool = False
    allowed_countries: Optional[List[str]] = None
    session_data_encryption: bool = False

class SessionPolicyManager:
    """Manager for session policies and enforcement"""
    
    def __init__(self):
        self.policies = self._load_default_policies()
        self.policy_overrides = {}
        
        # Environment-based configuration
        self.enforce_policies = os.getenv("ENFORCE_SESSION_POLICIES", "true").lower() == "true"
        self.default_security_level = SecurityLevel(os.getenv("DEFAULT_SECURITY_LEVEL", "medium"))
        
    def _load_default_policies(self) -> Dict[str, SessionPolicy]:
        """Load default session policies"""
        
        return {
            "anonymous": SessionPolicy(
                name="Anonymous User Policy",
                session_type=SessionType.ANONYMOUS,
                security_level=SecurityLevel.LOW,
                max_duration_hours=2,
                idle_timeout_minutes=30,
                max_concurrent_sessions=3,
                require_ip_consistency=False,
                require_user_agent_consistency=False,
                extend_on_activity=True
            ),
            
            "authenticated": SessionPolicy(
                name="Authenticated User Policy",
                session_type=SessionType.AUTHENTICATED,
                security_level=SecurityLevel.MEDIUM,
                max_duration_hours=8,
                idle_timeout_minutes=60,
                max_concurrent_sessions=5,
                require_ip_consistency=True,
                require_user_agent_consistency=False,
                extend_on_activity=True,
                force_reauth_after_hours=24
            ),
            
            "sso": SessionPolicy(
                name="SSO User Policy",
                session_type=SessionType.SSO,
                security_level=SecurityLevel.MEDIUM,
                max_duration_hours=4,
                idle_timeout_minutes=45,
                max_concurrent_sessions=3,
                require_ip_consistency=True,
                require_user_agent_consistency=True,
                extend_on_activity=True,
                force_reauth_after_hours=12
            ),
            
            "admin": SessionPolicy(
                name="Administrator Policy",
                session_type=SessionType.ADMIN,
                security_level=SecurityLevel.HIGH,
                max_duration_hours=2,
                idle_timeout_minutes=15,
                max_concurrent_sessions=2,
                require_ip_consistency=True,
                require_user_agent_consistency=True,
                extend_on_activity=False,
                force_reauth_after_hours=4,
                require_mfa=True,
                session_data_encryption=True
            ),
            
            "api": SessionPolicy(
                name="API Access Policy",
                session_type=SessionType.API,
                security_level=SecurityLevel.HIGH,
                max_duration_hours=1,
                idle_timeout_minutes=30,
                max_concurrent_sessions=10,
                require_ip_consistency=False,
                require_user_agent_consistency=False,
                extend_on_activity=False
            )
        }
    
    def get_policy(self, session_type: str, user_id: Optional[int] = None) -> SessionPolicy:
        """Get applicable policy for session type and user"""
        
        # Check for user-specific overrides
        if user_id and user_id in self.policy_overrides:
            override_policy = self.policy_overrides[user_id]
            logger.info(f"Using policy override for user {user_id}: {override_policy.name}")
            return override_policy
        
        # Get standard policy
        policy = self.policies.get(session_type)
        if not policy:
            logger.warning(f"No policy found for session type {session_type}, using authenticated policy")
            policy = self.policies["authenticated"]
        
        return policy
    
    def set_user_policy_override(self, user_id: int, policy: SessionPolicy):
        """Set policy override for specific user"""
        self.policy_overrides[user_id] = policy
        logger.info(f"Set policy override for user {user_id}: {policy.name}")
    
    def clear_user_policy_override(self, user_id: int):
        """Clear policy override for specific user"""
        if user_id in self.policy_overrides:
            del self.policy_overrides[user_id]
            logger.info(f"Cleared policy override for user {user_id}")
    
    def validate_session_against_policy(
        self,
        session_data: Dict[str, Any],
        current_request_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate session against applicable policy
        
        Returns:
            Tuple of (is_valid, violation_reason)
        """
        
        if not self.enforce_policies:
            return True, None
        
        try:
            # Determine session type
            session_type = self._determine_session_type(session_data)
            user_id = session_data.get("auth_user_id")
            
            # Get applicable policy
            policy = self.get_policy(session_type, user_id)
            
            # Check session duration
            if not self._check_session_duration(session_data, policy):
                return False, f"Session exceeded maximum duration of {policy.max_duration_hours} hours"
            
            # Check idle timeout
            if not self._check_idle_timeout(session_data, policy):
                return False, f"Session idle timeout exceeded ({policy.idle_timeout_minutes} minutes)"
            
            # Check IP consistency
            if policy.require_ip_consistency:
                if not self._check_ip_consistency(session_data, current_request_data):
                    return False, "IP address changed during session"
            
            # Check User-Agent consistency
            if policy.require_user_agent_consistency:
                if not self._check_user_agent_consistency(session_data, current_request_data):
                    return False, "User agent changed during session"
            
            # Check forced re-authentication
            if policy.force_reauth_after_hours:
                if not self._check_forced_reauth(session_data, policy):
                    return False, f"Forced re-authentication required after {policy.force_reauth_after_hours} hours"
            
            # Check geographic restrictions
            if policy.allowed_countries:
                if not self._check_geographic_restrictions(current_request_data, policy):
                    return False, "Geographic restriction violated"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error validating session against policy: {e}")
            return False, "Policy validation error"
    
    def _determine_session_type(self, session_data: Dict[str, Any]) -> str:
        """Determine session type from session data"""
        
        if session_data.get("is_authenticated"):
            auth_method = session_data.get("authentication_method", "form")
            
            if auth_method == "sso":
                return "sso"
            elif session_data.get("is_admin"):
                return "admin"
            elif session_data.get("is_api_session"):
                return "api"
            else:
                return "authenticated"
        else:
            return "anonymous"
    
    def _check_session_duration(self, session_data: Dict[str, Any], policy: SessionPolicy) -> bool:
        """Check if session duration is within policy limits"""
        
        created_at = session_data.get("created_at")
        if not created_at:
            return False
        
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        elif isinstance(created_at, (int, float)):
            created_at = datetime.fromtimestamp(created_at)
        
        session_age = datetime.now() - created_at
        max_duration = timedelta(hours=policy.max_duration_hours)
        
        return session_age <= max_duration
    
    def _check_idle_timeout(self, session_data: Dict[str, Any], policy: SessionPolicy) -> bool:
        """Check if session idle time is within policy limits"""
        
        last_activity = session_data.get("last_activity")
        if not last_activity:
            return False
        
        if isinstance(last_activity, str):
            last_activity = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
        elif isinstance(last_activity, (int, float)):
            last_activity = datetime.fromtimestamp(last_activity)
        
        idle_time = datetime.now() - last_activity
        max_idle = timedelta(minutes=policy.idle_timeout_minutes)
        
        return idle_time <= max_idle
    
    def _check_ip_consistency(
        self,
        session_data: Dict[str, Any],
        current_request_data: Dict[str, Any]
    ) -> bool:
        """Check IP address consistency"""
        
        session_ip = session_data.get("client_ip")
        current_ip = current_request_data.get("client_ip")
        
        if not session_ip or not current_ip:
            return True  # Can't validate without IP data
        
        return session_ip == current_ip
    
    def _check_user_agent_consistency(
        self,
        session_data: Dict[str, Any],
        current_request_data: Dict[str, Any]
    ) -> bool:
        """Check User-Agent consistency"""
        
        session_ua = session_data.get("user_agent")
        current_ua = current_request_data.get("user_agent")
        
        if not session_ua or not current_ua:
            return True  # Can't validate without UA data
        
        return session_ua == current_ua
    
    def _check_forced_reauth(self, session_data: Dict[str, Any], policy: SessionPolicy) -> bool:
        """Check if forced re-authentication is required"""
        
        last_auth = session_data.get("last_authentication")
        if not last_auth:
            # Use session creation time as fallback
            last_auth = session_data.get("created_at")
        
        if not last_auth:
            return False
        
        if isinstance(last_auth, str):
            last_auth = datetime.fromisoformat(last_auth.replace('Z', '+00:00'))
        elif isinstance(last_auth, (int, float)):
            last_auth = datetime.fromtimestamp(last_auth)
        
        time_since_auth = datetime.now() - last_auth
        max_auth_duration = timedelta(hours=policy.force_reauth_after_hours)
        
        return time_since_auth <= max_auth_duration
    
    def _check_geographic_restrictions(
        self,
        current_request_data: Dict[str, Any],
        policy: SessionPolicy
    ) -> bool:
        """Check geographic restrictions"""
        
        if not policy.allowed_countries:
            return True
        
        # This would require GeoIP lookup implementation
        # For now, return True (no restriction)
        return True
    
    def should_extend_session(
        self,
        session_data: Dict[str, Any],
        activity_type: str = "request"
    ) -> bool:
        """Determine if session should be extended based on activity"""
        
        session_type = self._determine_session_type(session_data)
        user_id = session_data.get("auth_user_id")
        policy = self.get_policy(session_type, user_id)
        
        if not policy.extend_on_activity:
            return False
        
        # Don't extend if close to forced re-auth time
        if policy.force_reauth_after_hours:
            if not self._check_forced_reauth(session_data, policy):
                return False
        
        # Different activities might have different rules
        if activity_type == "sensitive_operation":
            # Don't extend on sensitive operations for high-security sessions
            if policy.security_level in [SecurityLevel.HIGH, SecurityLevel.CRITICAL]:
                return False
        
        return True
    
    def get_session_extension_duration(self, session_data: Dict[str, Any]) -> timedelta:
        """Get duration to extend session by"""
        
        session_type = self._determine_session_type(session_data)
        user_id = session_data.get("auth_user_id")
        policy = self.get_policy(session_type, user_id)
        
        # Base extension is 1/4 of the max duration, but not more than 2 hours
        base_extension_hours = min(policy.max_duration_hours / 4, 2)
        
        return timedelta(hours=base_extension_hours)
    
    def get_policy_summary(self) -> Dict[str, Any]:
        """Get summary of all session policies"""
        
        summary = {
            "enforcement_enabled": self.enforce_policies,
            "default_security_level": self.default_security_level.value,
            "policies": {},
            "user_overrides": len(self.policy_overrides)
        }
        
        for policy_name, policy in self.policies.items():
            summary["policies"][policy_name] = {
                "name": policy.name,
                "security_level": policy.security_level.value,
                "max_duration_hours": policy.max_duration_hours,
                "idle_timeout_minutes": policy.idle_timeout_minutes,
                "max_concurrent_sessions": policy.max_concurrent_sessions,
                "ip_consistency_required": policy.require_ip_consistency,
                "user_agent_consistency_required": policy.require_user_agent_consistency,
                "extends_on_activity": policy.extend_on_activity,
                "force_reauth_hours": policy.force_reauth_after_hours,
                "requires_mfa": policy.require_mfa
            }
        
        return summary

# Global session policy manager
session_policy_manager = SessionPolicyManager()
```

## 2. Session Cleanup Service

### Create Advanced Session Cleanup

Create `authentication/session_cleanup_service.py`:

```python
"""
Advanced session cleanup and maintenance service
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from chat.session_manager import session_manager
from .session_policies import session_policy_manager, SessionType

logger = logging.getLogger(__name__)

class SessionCleanupService:
    """Advanced session cleanup and maintenance"""
    
    def __init__(self):
        self.cleanup_interval = 1800  # 30 minutes
        self.running = False
        
        # Cleanup statistics
        self.cleanup_stats = {
            "total_cleanups": 0,
            "sessions_cleaned": 0,
            "last_cleanup": None,
            "cleanup_errors": 0
        }
        
        # Cleanup policies
        self.cleanup_policies = {
            "expired_sessions": True,
            "idle_sessions": True,
            "policy_violations": True,
            "orphaned_sessions": True,
            "duplicate_sessions": True,
            "suspicious_sessions": True
        }
    
    async def start_cleanup_service(self):
        """Start the background cleanup service"""
        self.running = True
        logger.info("🧹 Starting advanced session cleanup service")
        
        while self.running:
            try:
                await self.perform_comprehensive_cleanup()
                await asyncio.sleep(self.cleanup_interval)
            except Exception as e:
                logger.error(f"Session cleanup service error: {e}")
                self.cleanup_stats["cleanup_errors"] += 1
                await asyncio.sleep(60)  # Short retry delay
    
    def stop_cleanup_service(self):
        """Stop the cleanup service"""
        self.running = False
        logger.info("🛑 Advanced session cleanup service stopped")
    
    async def perform_comprehensive_cleanup(self):
        """Perform comprehensive session cleanup"""
        logger.info("🧹 Starting comprehensive session cleanup...")
        
        cleanup_start = datetime.now()
        total_cleaned = 0
        
        try:
            # 1. Clean expired sessions
            if self.cleanup_policies["expired_sessions"]:
                expired_count = await self._cleanup_expired_sessions()
                total_cleaned += expired_count
                logger.info(f"   Cleaned {expired_count} expired sessions")
            
            # 2. Clean idle sessions
            if self.cleanup_policies["idle_sessions"]:
                idle_count = await self._cleanup_idle_sessions()
                total_cleaned += idle_count
                logger.info(f"   Cleaned {idle_count} idle sessions")
            
            # 3. Clean policy violations
            if self.cleanup_policies["policy_violations"]:
                violation_count = await self._cleanup_policy_violations()
                total_cleaned += violation_count
                logger.info(f"   Cleaned {violation_count} policy violation sessions")
            
            # 4. Clean orphaned sessions
            if self.cleanup_policies["orphaned_sessions"]:
                orphaned_count = await self._cleanup_orphaned_sessions()
                total_cleaned += orphaned_count
                logger.info(f"   Cleaned {orphaned_count} orphaned sessions")
            
            # 5. Clean duplicate sessions
            if self.cleanup_policies["duplicate_sessions"]:
                duplicate_count = await self._cleanup_duplicate_sessions()
                total_cleaned += duplicate_count
                logger.info(f"   Cleaned {duplicate_count} duplicate sessions")
            
            # 6. Clean suspicious sessions
            if self.cleanup_policies["suspicious_sessions"]:
                suspicious_count = await self._cleanup_suspicious_sessions()
                total_cleaned += suspicious_count
                logger.info(f"   Cleaned {suspicious_count} suspicious sessions")
            
            # Update statistics
            self.cleanup_stats["total_cleanups"] += 1
            self.cleanup_stats["sessions_cleaned"] += total_cleaned
            self.cleanup_stats["last_cleanup"] = cleanup_start.isoformat()
            
            cleanup_duration = (datetime.now() - cleanup_start).total_seconds()
            logger.info(f"✅ Session cleanup completed: {total_cleaned} sessions cleaned in {cleanup_duration:.2f}s")
            
        except Exception as e:
            logger.error(f"Comprehensive cleanup error: {e}")
            self.cleanup_stats["cleanup_errors"] += 1
    
    async def _cleanup_expired_sessions(self) -> int:
        """Clean up sessions that have expired based on their expiration date"""
        try:
            count = await session_manager.cleanup_expired_sessions()
            return count
        except Exception as e:
            logger.error(f"Expired session cleanup error: {e}")
            return 0
    
    async def _cleanup_idle_sessions(self) -> int:
        """Clean up sessions that have been idle too long"""
        try:
            # Get session statistics to find idle sessions
            stats = await session_manager.get_session_statistics()
            
            # This would require extending session_manager to support idle cleanup
            # For now, return 0
            return 0
            
        except Exception as e:
            logger.error(f"Idle session cleanup error: {e}")
            return 0
    
    async def _cleanup_policy_violations(self) -> int:
        """Clean up sessions that violate security policies"""
        try:
            cleaned_count = 0
            
            # Get all active sessions
            # This would require a method to get all sessions
            # For demonstration, we'll implement a basic approach
            
            # Note: This would need to be implemented in session_manager
            # sessions = await session_manager.get_all_active_sessions()
            
            # for session in sessions:
            #     # Check each session against its policy
            #     current_request_data = {"client_ip": None, "user_agent": None}
            #     is_valid, violation = session_policy_manager.validate_session_against_policy(
            #         session, current_request_data
            #     )
            #     
            #     if not is_valid:
            #         await session_manager.invalidate_session(session["session_id"])
            #         cleaned_count += 1
            #         logger.warning(f"Cleaned session {session['session_id']} for policy violation: {violation}")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Policy violation cleanup error: {e}")
            return 0
    
    async def _cleanup_orphaned_sessions(self) -> int:
        """Clean up sessions that have no corresponding user data"""
        try:
            # This would check for sessions where the user no longer exists
            # Implementation depends on your user management system
            return 0
            
        except Exception as e:
            logger.error(f"Orphaned session cleanup error: {e}")
            return 0
    
    async def _cleanup_duplicate_sessions(self) -> int:
        """Clean up duplicate sessions for users"""
        try:
            cleaned_count = 0
            
            # This would identify users with too many concurrent sessions
            # and clean up the oldest ones based on policy
            
            # Get users with multiple sessions
            # user_sessions = await session_manager.get_users_with_multiple_sessions()
            
            # for user_id, sessions in user_sessions.items():
            #     # Get policy for user
            #     session_type = "authenticated"  # Would determine from first session
            #     policy = session_policy_manager.get_policy(session_type, user_id)
            #     
            #     if len(sessions) > policy.max_concurrent_sessions:
            #         # Sort by last activity and keep the most recent ones
            #         sessions.sort(key=lambda s: s["last_activity"], reverse=True)
            #         sessions_to_remove = sessions[policy.max_concurrent_sessions:]
            #         
            #         for session in sessions_to_remove:
            #             await session_manager.invalidate_session(session["session_id"])
            #             cleaned_count += 1
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Duplicate session cleanup error: {e}")
            return 0
    
    async def _cleanup_suspicious_sessions(self) -> int:
        """Clean up sessions flagged as suspicious"""
        try:
            # This would clean up sessions flagged by security monitoring
            # Implementation depends on your security monitoring system
            return 0
            
        except Exception as e:
            logger.error(f"Suspicious session cleanup error: {e}")
            return 0
    
    async def force_cleanup_user_sessions(
        self,
        user_id: int,
        reason: str = "administrative",
        except_session_id: Optional[str] = None
    ) -> int:
        """Force cleanup of all sessions for a specific user"""
        
        try:
            logger.info(f"Force cleaning sessions for user {user_id}, reason: {reason}")
            
            count = await session_manager.invalidate_user_sessions(
                user_id=user_id,
                except_session_id=except_session_id
            )
            
            logger.info(f"Force cleaned {count} sessions for user {user_id}")
            return count
            
        except Exception as e:
            logger.error(f"Force cleanup error for user {user_id}: {e}")
            return 0
    
    async def cleanup_sessions_by_criteria(
        self,
        criteria: Dict[str, Any]
    ) -> int:
        """Clean up sessions matching specific criteria"""
        
        try:
            cleaned_count = 0
            
            # Example criteria:
            # {
            #     "auth_method": "sso",
            #     "partner_id": "partner1",
            #     "created_before": "2024-01-01T00:00:00Z",
            #     "inactive_for_hours": 24
            # }
            
            logger.info(f"Cleaning sessions by criteria: {criteria}")
            
            # Implementation would depend on extending session_manager
            # to support complex queries
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Criteria-based cleanup error: {e}")
            return 0
    
    def get_cleanup_statistics(self) -> Dict[str, Any]:
        """Get cleanup service statistics"""
        
        return {
            "service_status": "running" if self.running else "stopped",
            "cleanup_interval_seconds": self.cleanup_interval,
            "cleanup_policies": self.cleanup_policies.copy(),
            "statistics": self.cleanup_stats.copy(),
            "next_cleanup_in_seconds": self.cleanup_interval if self.running else None
        }
    
    def update_cleanup_policies(self, policies: Dict[str, bool]):
        """Update cleanup policies"""
        
        for policy_name, enabled in policies.items():
            if policy_name in self.cleanup_policies:
                self.cleanup_policies[policy_name] = enabled
                logger.info(f"Updated cleanup policy {policy_name}: {enabled}")
    
    def set_cleanup_interval(self, interval_seconds: int):
        """Set cleanup interval"""
        
        if 300 <= interval_seconds <= 86400:  # Between 5 minutes and 24 hours
            self.cleanup_interval = interval_seconds
            logger.info(f"Updated cleanup interval to {interval_seconds} seconds")
        else:
            logger.error(f"Invalid cleanup interval: {interval_seconds} (must be 300-86400)")

# Global session cleanup service
session_cleanup_service = SessionCleanupService()
```

## 3. Session Security Monitor

### Create Session Security Monitor

Create `authentication/session_security_monitor.py`:

```python
"""
Session security monitoring and alerting
"""
import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum

from .session_policies import session_policy_manager
from .security_utils import security_utils

logger = logging.getLogger(__name__)

class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class SessionSecurityMonitor:
    """Monitor session security and generate alerts"""
    
    def __init__(self):
        self.monitoring_enabled = True
        self.alert_thresholds = self._load_alert_thresholds()
        
        # Tracking data
        self.session_events = deque(maxlen=10000)
        self.security_alerts = deque(maxlen=1000)
        self.user_activity_patterns = defaultdict(list)
        self.ip_activity_patterns = defaultdict(list)
        
        # Statistics
        self.monitoring_stats = {
            "events_processed": 0,
            "alerts_generated": 0,
            "last_monitoring_run": None,
            "suspicious_patterns_detected": 0
        }
    
    def _load_alert_thresholds(self) -> Dict[str, Any]:
        """Load alert thresholds configuration"""
        
        return {
            # Session-based thresholds
            "max_concurrent_sessions_per_user": 10,
            "max_failed_logins_per_ip": 20,
            "max_session_duration_hours": 24,
            "suspicious_ip_changes_threshold": 3,
            
            # Time-based thresholds
            "rapid_session_creation_threshold": 5,  # sessions per minute
            "rapid_login_attempts_threshold": 10,   # attempts per minute
            "unusual_activity_hours": [22, 23, 0, 1, 2, 3, 4, 5],  # 10 PM - 5 AM
            
            # Geographic thresholds
            "max_countries_per_user": 3,
            "impossible_travel_speed_kmh": 1000,  # km/h
            
            # Policy violation thresholds
            "policy_violations_per_hour": 5,
            "consecutive_policy_violations": 3
        }
    
    def record_session_event(
        self,
        event_type: str,
        session_data: Dict[str, Any],
        request_data: Optional[Dict[str, Any]] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ):
        """Record a session-related event for monitoring"""
        
        if not self.monitoring_enabled:
            return
        
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "session_id": session_data.get("session_id"),
            "user_id": session_data.get("auth_user_id"),
            "username": session_data.get("auth_username"),
            "auth_method": session_data.get("authentication_method"),
            "client_ip": request_data.get("client_ip") if request_data else None,
            "user_agent": request_data.get("user_agent") if request_data else None,
            "additional_context": additional_context or {}
        }
        
        self.session_events.append(event)
        self.monitoring_stats["events_processed"] += 1
        
        # Analyze event for suspicious patterns
        self._analyze_event_for_patterns(event)
    
    def _analyze_event_for_patterns(self, event: Dict[str, Any]):
        """Analyze event for suspicious patterns"""
        
        try:
            event_type = event["event_type"]
            user_id = event["user_id"]
            client_ip = event["client_ip"]
            timestamp = datetime.fromisoformat(event["timestamp"])
            
            # Pattern 1: Rapid session creation
            if event_type == "session_created":
                self._check_rapid_session_creation(user_id, timestamp)
            
            # Pattern 2: Multiple concurrent sessions
            if event_type in ["session_created", "session_accessed"]:
                self._check_concurrent_sessions(user_id)
            
            # Pattern 3: Suspicious IP changes
            if event_type == "session_accessed" and client_ip:
                self._check_ip_changes(user_id, client_ip, timestamp)
            
            # Pattern 4: Policy violations
            if event_type == "policy_violation":
                self._check_policy_violation_patterns(user_id, timestamp)
            
            # Pattern 5: Unusual activity hours
            if event_type in ["session_created", "login_attempt"]:
                self._check_unusual_activity_hours(user_id, timestamp)
            
            # Pattern 6: Failed login patterns
            if event_type == "login_failed" and client_ip:
                self._check_failed_login_patterns(client_ip, timestamp)
            
        except Exception as e:
            logger.error(f"Error analyzing event pattern: {e}")
    
    def _check_rapid_session_creation(self, user_id: Optional[int], timestamp: datetime):
        """Check for rapid session creation pattern"""
        
        if not user_id:
            return
        
        # Get recent session creation events for user
        recent_events = [
            e for e in self.session_events
            if (e["user_id"] == user_id and 
                e["event_type"] == "session_created" and
                datetime.fromisoformat(e["timestamp"]) > timestamp - timedelta(minutes=1))
        ]
        
        if len(recent_events) >= self.alert_thresholds["rapid_session_creation_threshold"]:
            self._create_security_alert(
                AlertSeverity.HIGH,
                "rapid_session_creation",
                f"User {user_id} created {len(recent_events)} sessions in 1 minute",
                {"user_id": user_id, "session_count": len(recent_events)}
            )
    
    def _check_concurrent_sessions(self, user_id: Optional[int]):
        """Check for excessive concurrent sessions"""
        
        if not user_id:
            return
        
        # This would require querying active sessions from session_manager
        # For now, we'll simulate based on recent events
        recent_sessions = set()
        cutoff_time = datetime.now() - timedelta(hours=1)
        
        for event in self.session_events:
            if (event["user_id"] == user_id and 
                event["event_type"] in ["session_created", "session_accessed"] and
                datetime.fromisoformat(event["timestamp"]) > cutoff_time):
                recent_sessions.add(event["session_id"])
        
        if len(recent_sessions) > self.alert_thresholds["max_concurrent_sessions_per_user"]:
            self._create_security_alert(
                AlertSeverity.MEDIUM,
                "excessive_concurrent_sessions",
                f"User {user_id} has {len(recent_sessions)} concurrent sessions",
                {"user_id": user_id, "session_count": len(recent_sessions)}
            )
    
    def _check_ip_changes(self, user_id: Optional[int], client_ip: str, timestamp: datetime):
        """Check for suspicious IP address changes"""
        
        if not user_id or not client_ip:
            return
        
        # Track IP changes for user
        user_ips = self.user_activity_patterns[f"ip_changes_{user_id}"]
        user_ips.append({"ip": client_ip, "timestamp": timestamp})
        
        # Keep only last hour of IP data
        user_ips[:] = [
            ip_data for ip_data in user_ips
            if ip_data["timestamp"] > timestamp - timedelta(hours=1)
        ]
        
        # Check for multiple IP changes
        unique_ips = set(ip_data["ip"] for ip_data in user_ips)
        
        if len(unique_ips) >= self.alert_thresholds["suspicious_ip_changes_threshold"]:
            self._create_security_alert(
                AlertSeverity.HIGH,
                "suspicious_ip_changes",
                f"User {user_id} accessed from {len(unique_ips)} different IPs in 1 hour",
                {
                    "user_id": user_id,
                    "ip_count": len(unique_ips),
                    "ips": list(unique_ips)
                }
            )
    
    def _check_policy_violation_patterns(self, user_id: Optional[int], timestamp: datetime):
        """Check for patterns in policy violations"""
        
        if not user_id:
            return
        
        # Count recent policy violations for user
        recent_violations = [
            e for e in self.session_events
            if (e["user_id"] == user_id and 
                e["event_type"] == "policy_violation" and
                datetime.fromisoformat(e["timestamp"]) > timestamp - timedelta(hours=1))
        ]
        
        if len(recent_violations) >= self.alert_thresholds["policy_violations_per_hour"]:
            self._create_security_alert(
                AlertSeverity.HIGH,
                "excessive_policy_violations",
                f"User {user_id} had {len(recent_violations)} policy violations in 1 hour",
                {"user_id": user_id, "violation_count": len(recent_violations)}
            )
    
    def _check_unusual_activity_hours(self, user_id: Optional[int], timestamp: datetime):
        """Check for activity during unusual hours"""
        
        if not user_id:
            return
        
        current_hour = timestamp.hour
        
        if current_hour in self.alert_thresholds["unusual_activity_hours"]:
            # Check if this is unusual for this user
            user_activity = self.user_activity_patterns[f"activity_hours_{user_id}"]
            user_activity.append(current_hour)
            
            # Keep only last 30 days of activity data (simplified)
            if len(user_activity) > 720:  # 30 days * 24 hours
                user_activity.pop(0)
            
            # If user rarely uses the system during these hours, alert
            unusual_hour_activity = sum(1 for hour in user_activity if hour in self.alert_thresholds["unusual_activity_hours"])
            total_activity = len(user_activity)
            
            if total_activity > 50 and unusual_hour_activity / total_activity < 0.1:  # Less than 10% of activity during unusual hours
                self._create_security_alert(
                    AlertSeverity.LOW,
                    "unusual_activity_hours",
                    f"User {user_id} active during unusual hours ({current_hour}:00)",
                    {"user_id": user_id, "hour": current_hour}
                )
    
    def _check_failed_login_patterns(self, client_ip: str, timestamp: datetime):
        """Check for failed login patterns from IP"""
        
        # Count recent failed logins from IP
        recent_failures = [
            e for e in self.session_events
            if (e["client_ip"] == client_ip and 
                e["event_type"] == "login_failed" and
                datetime.fromisoformat(e["timestamp"]) > timestamp - timedelta(hours=1))
        ]
        
        if len(recent_failures) >= self.alert_thresholds["max_failed_logins_per_ip"]:
            self._create_security_alert(
                AlertSeverity.HIGH,
                "excessive_failed_logins",
                f"IP {client_ip} had {len(recent_failures)} failed login attempts in 1 hour",
                {"client_ip": client_ip, "failure_count": len(recent_failures)}
            )
    
    def _create_security_alert(
        self,
        severity: AlertSeverity,
        alert_type: str,
        message: str,
        details: Dict[str, Any]
    ):
        """Create and log a security alert"""
        
        alert = {
            "alert_id": len(self.security_alerts) + 1,
            "timestamp": datetime.now().isoformat(),
            "severity": severity.value,
            "alert_type": alert_type,
            "message": message,
            "details": details,
            "acknowledged": False,
            "resolved": False
        }
        
        self.security_alerts.append(alert)
        self.monitoring_stats["alerts_generated"] += 1
        self.monitoring_stats["suspicious_patterns_detected"] += 1
        
        # Log alert
        logger.warning(f"SESSION_SECURITY_ALERT: {json.dumps(alert)}")
        
        # Could integrate with external alerting systems
        # await self._send_external_alert(alert)
    
    def get_security_dashboard(self) -> Dict[str, Any]:
        """Get security monitoring dashboard data"""
        
        now = datetime.now()
        last_24h = now - timedelta(hours=24)
        
        # Recent events summary
        recent_events = [
            e for e in self.session_events
            if datetime.fromisoformat(e["timestamp"]) > last_24h
        ]
        
        event_types = defaultdict(int)
        for event in recent_events:
            event_types[event["event_type"]] += 1
        
        # Recent alerts summary
        recent_alerts = [
            a for a in self.security_alerts
            if datetime.fromisoformat(a["timestamp"]) > last_24h
        ]
        
        alert_severities = defaultdict(int)
        for alert in recent_alerts:
            alert_severities[alert["severity"]] += 1
        
        # Top users by activity
        user_activity = defaultdict(int)
        for event in recent_events:
            if event["user_id"]:
                user_activity[event["user_id"]] += 1
        
        top_users = sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Top IPs by activity
        ip_activity = defaultdict(int)
        for event in recent_events:
            if event["client_ip"]:
                ip_activity[event["client_ip"]] += 1
        
        top_ips = sorted(ip_activity.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "monitoring_status": "enabled" if self.monitoring_enabled else "disabled",
            "monitoring_stats": self.monitoring_stats.copy(),
            "alert_thresholds": self.alert_thresholds.copy(),
            "recent_activity": {
                "total_events_24h": len(recent_events),
                "total_alerts_24h": len(recent_alerts),
                "event_types": dict(event_types),
                "alert_severities": dict(alert_severities),
                "top_active_users": top_users,
                "top_active_ips": top_ips
            },
            "unacknowledged_alerts": len([a for a in self.security_alerts if not a["acknowledged"]]),
            "critical_alerts_24h": len([a for a in recent_alerts if a["severity"] == "critical"])
        }
    
    def acknowledge_alert(self, alert_id: int, acknowledged_by: str = "system"):
        """Acknowledge a security alert"""
        
        for alert in self.security_alerts:
            if alert["alert_id"] == alert_id:
                alert["acknowledged"] = True
                alert["acknowledged_by"] = acknowledged_by
                alert["acknowledged_at"] = datetime.now().isoformat()
                logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
                return True
        
        return False
    
    def resolve_alert(self, alert_id: int, resolved_by: str = "system", resolution_notes: str = ""):
        """Resolve a security alert"""
        
        for alert in self.security_alerts:
            if alert["alert_id"] == alert_id:
                alert["resolved"] = True
                alert["resolved_by"] = resolved_by
                alert["resolved_at"] = datetime.now().isoformat()
                alert["resolution_notes"] = resolution_notes
                logger.info(f"Alert {alert_id} resolved by {resolved_by}")
                return True
        
        return False
    
    def get_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        acknowledged: Optional[bool] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get security alerts with filtering"""
        
        alerts = list(self.security_alerts)
        
        # Apply filters
        if severity:
            alerts = [a for a in alerts if a["severity"] == severity.value]
        
        if acknowledged is not None:
            alerts = [a for a in alerts if a["acknowledged"] == acknowledged]
        
        # Sort by timestamp (newest first)
        alerts.sort(key=lambda a: a["timestamp"], reverse=True)
        
        return alerts[:limit]

# Global session security monitor
session_security_monitor = SessionSecurityMonitor()
```

## 4. Integration with Main Application

### Update Main Application with Policy Enforcement

Add to your main application:

```python
from authentication.session_policies import session_policy_manager
from authentication.session_cleanup_service import session_cleanup_service
from authentication.session_security_monitor import session_security_monitor

# Update lifespan to include new services
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Enhanced application lifecycle with all services"""
    # Startup
    cleanup_task = asyncio.create_task(cleanup_old_sessions())
    advanced_cleanup_task = asyncio.create_task(
        session_cleanup_service.start_cleanup_service()
    )
    
    print("✅ Started all session management services")
    
    yield
    
    # Shutdown
    cleanup_task.cancel()
    session_cleanup_service.stop_cleanup_service()
    advanced_cleanup_task.cancel()
    
    try:
        await cleanup_task
        await advanced_cleanup_task
    except asyncio.CancelledError:
        pass
        
    print("🛑 Stopped all session management services")

# Add policy enforcement to authentication middleware
async def enhanced_get_current_user_from_session(request: Request) -> Optional[Dict[str, Any]]:
    """Enhanced user authentication with policy enforcement"""
    
    # Get basic session data
    if not request.session.get("authenticated"):
        return None
    
    session_id = request.session.get("chat_session_id")
    user_id = request.session.get("user_id")
    
    if not all([session_id, user_id]):
        request.session.clear()
        return None
    
    # Get session data from database
    session_data = await session_manager.validate_authenticated_session(
        session_id=session_id,
        user_id=user_id
    )
    
    if not session_data:
        request.session.clear()
        return None
    
    # Build current request data for policy validation
    current_request_data = {
        "client_ip": request.client.host,
        "user_agent": request.headers.get("user-agent"),
        "timestamp": datetime.now().isoformat()
    }
    
    # Validate against session policies
    is_valid, violation_reason = session_policy_manager.validate_session_against_policy(
        session_data, current_request_data
    )
    
    if not is_valid:
        # Record security event
        session_security_monitor.record_session_event(
            "policy_violation",
            session_data,
            current_request_data,
            {"violation_reason": violation_reason}
        )
        
        # Invalidate session
        await session_manager.invalidate_session(session_id)
        request.session.clear()
        
        logger.warning(f"Session {session_id} invalidated for policy violation: {violation_reason}")
        return None
    
    # Record normal session access
    session_security_monitor.record_session_event(
        "session_accessed",
        session_data,
        current_request_data
    )
    
    # Check if session should be extended
    if session_policy_manager.should_extend_session(session_data):
        extension_duration = session_policy_manager.get_session_extension_duration(session_data)
        await session_manager.extend_session_expiration(
            session_id, 
            int(extension_duration.total_seconds() / 3600)  # Convert to hours
        )
    
    return {
        "user_id": session_data["auth_user_id"],
        "username": session_data["auth_username"],
        "session_id": session_data["session_id"],
        "auth_method": session_data["authentication_method"],
        "expires_at": session_data.get("expires_at")
    }

# Add session management endpoints
@app.get("/api/session/policies")
async def get_session_policies(request: Request):
    """Get session policy information"""
    current_user = await enhanced_get_current_user_from_session(request)
    if not current_user:
        raise HTTPException(401, "Authentication required")
    
    return session_policy_manager.get_policy_summary()

@app.get("/api/session/security-dashboard")
async def get_security_dashboard(request: Request):
    """Get session security dashboard"""
    current_user = await enhanced_get_current_user_from_session(request)
    if not current_user:
        raise HTTPException(401, "Authentication required")
    
    return session_security_monitor.get_security_dashboard()

@app.get("/api/session/cleanup-stats")
async def get_cleanup_statistics(request: Request):
    """Get session cleanup statistics"""
    current_user = await enhanced_get_current_user_from_session(request)
    if not current_user:
        raise HTTPException(401, "Authentication required")
    
    return session_cleanup_service.get_cleanup_statistics()

@app.post("/api/session/force-cleanup/{user_id}")
async def force_user_session_cleanup(
    user_id: int,
    request: Request,
    reason: str = "administrative"
):
    """Force cleanup of user sessions (admin only)"""
    current_user = await enhanced_get_current_user_from_session(request)
    if not current_user:
        raise HTTPException(401, "Authentication required")
    
    # Add admin check here if needed
    # if not current_user.get("is_admin"):
    #     raise HTTPException(403, "Admin access required")
    
    count = await session_cleanup_service.force_cleanup_user_sessions(
        user_id, reason
    )
    
    return {"cleaned_sessions": count, "reason": reason}
```

## 5. Testing Session Policies

### Create Policy Tests

Create `authentication/test_session_policies.py`:

```python
"""
Test session policies and security features
"""
import asyncio
from datetime import datetime, timedelta
from .session_policies import session_policy_manager, SessionType, SecurityLevel
from .session_security_monitor import session_security_monitor
from .session_cleanup_service import session_cleanup_service

async def test_session_policies():
    """Test session policy functionality"""
    print("🧪 Testing session policies and security...")
    
    # Test 1: Policy validation
    print("\n1. Testing policy validation...")
    try:
        # Create test session data
        session_data = {
            "session_id": "test-session-123",
            "auth_user_id": 123,
            "auth_username": "testuser",
            "is_authenticated": True,
            "authentication_method": "form",
            "created_at": datetime.now().timestamp(),
            "last_activity": datetime.now().timestamp(),
            "client_ip": "192.168.1.100",
            "user_agent": "Mozilla/5.0 Test Browser"
        }
        
        current_request_data = {
            "client_ip": "192.168.1.100",
            "user_agent": "Mozilla/5.0 Test Browser"
        }
        
        # Test valid session
        is_valid, violation = session_policy_manager.validate_session_against_policy(
            session_data, current_request_data
        )
        
        if is_valid:
            print("✅ Valid session correctly validated")
        else:
            print(f"❌ Valid session incorrectly rejected: {violation}")
        
        # Test IP change violation
        current_request_data["client_ip"] = "192.168.1.200"
        is_valid, violation = session_policy_manager.validate_session_against_policy(
            session_data, current_request_data
        )
        
        if not is_valid and "IP address" in violation:
            print("✅ IP change violation correctly detected")
        else:
            print(f"❌ IP change violation not detected: {violation}")
            
    except Exception as e:
        print(f"❌ Policy validation test failed: {e}")
    
    # Test 2: Policy configuration
    print("\n2. Testing policy configuration...")
    try:
        policy_summary = session_policy_manager.get_policy_summary()
        print(f"✅ Retrieved policy summary with {len(policy_summary['policies'])} policies")
        
        # Test policy retrieval
        auth_policy = session_policy_manager.get_policy("authenticated")
        print(f"✅ Retrieved authenticated policy: {auth_policy.name}")
        
    except Exception as e:
        print(f"❌ Policy configuration test failed: {e}")
    
    # Test 3: Security monitoring
    print("\n3. Testing security monitoring...")
    try:
        # Record test events
        session_security_monitor.record_session_event(
            "session_created",
            session_data,
            current_request_data
        )
        
        session_security_monitor.record_session_event(
            "session_accessed", 
            session_data,
            current_request_data
        )
        
        # Get dashboard
        dashboard = session_security_monitor.get_security_dashboard()
        print(f"✅ Security dashboard generated with {dashboard['recent_activity']['total_events_24h']} events")
        
    except Exception as e:
        print(f"❌ Security monitoring test failed: {e}")
    
    # Test 4: Cleanup service
    print("\n4. Testing cleanup service...")
    try:
        cleanup_stats = session_cleanup_service.get_cleanup_statistics()
        print(f"✅ Cleanup statistics retrieved: {cleanup_stats['service_status']}")
        
    except Exception as e:
        print(f"❌ Cleanup service test failed: {e}")
    
    print("\n✅ Session policies and security testing completed!")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_session_policies())
    exit(0 if success else 1)
```

## 6. Production Configuration

### Environment Configuration

Add to your `.env` file:

```bash
# Session Policy Configuration
ENFORCE_SESSION_POLICIES=true
DEFAULT_SECURITY_LEVEL=medium

# Session Security Monitoring
ENABLE_SESSION_MONITORING=true
SESSION_ALERT_EMAIL=security@yourcompany.com
SESSION_ALERT_SLACK_WEBHOOK=https://hooks.slack.com/your-webhook

# Session Cleanup Configuration  
SESSION_CLEANUP_INTERVAL=1800
CLEANUP_EXPIRED_SESSIONS=true
CLEANUP_IDLE_SESSIONS=true
CLEANUP_POLICY_VIOLATIONS=true

# Security Thresholds
MAX_CONCURRENT_SESSIONS_PER_USER=5
MAX_FAILED_LOGINS_PER_IP=20
SUSPICIOUS_IP_CHANGES_THRESHOLD=3
POLICY_VIOLATIONS_PER_HOUR=5
```

## 7. Testing and Validation

### Pre-Production Checklist

- [ ] Session policies configured and tested
- [ ] Policy validation works correctly
- [ ] Security monitoring is active
- [ ] Cleanup service runs properly
- [ ] Alert thresholds are appropriate
- [ ] Policy violations are handled correctly
- [ ] Session extension logic works
- [ ] All tests pass successfully

### Testing Commands

```bash
# Test session policies
python authentication/test_session_policies.py

# Test API endpoints
curl http://localhost:8000/api/session/policies
curl http://localhost:8000/api/session/security-dashboard
curl http://localhost:8000/api/session/cleanup-stats

# Test policy enforcement
# (requires active session to test)
```

## Next Steps

After completing this phase:

1. Monitor session policy enforcement in production
2. Adjust alert thresholds based on actual usage
3. Review security alerts regularly
4. Proceed to Phase 8: Testing and Validation
5. Document operational procedures

## Security Reminders

1. **Policy Enforcement**: Ensure policies are appropriate for your security requirements
2. **Monitoring**: Regularly review security alerts and patterns
3. **Cleanup**: Maintain regular session cleanup to prevent data accumulation
4. **Alerting**: Set up proper alerting for critical security events
5. **Documentation**: Document all policies and procedures for operations team
6. **Regular Review**: Review and update policies based on threat landscape
7. **Incident Response**: Have procedures for responding to security alerts
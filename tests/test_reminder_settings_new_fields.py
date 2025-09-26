import uuid
import pytest
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from fs_flowstate_svc.models.flowstate_models import Users, Events, ReminderSettings


class TestReminderSettingsNewFields:
    """Test the new fields added to ReminderSettings model for tracking reminder delivery status and notification methods."""
    
    def test_create_reminder_with_default_values(self, db_session):
        """Test creating a reminder setting with default values for new fields."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        event = Events(
            user_id=user.id,
            title="Test Event",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1)
        )
        db_session.add(event)
        db_session.commit()
        
        reminder = ReminderSettings(
            user_id=user.id,
            event_id=event.id,
            reminder_time=datetime.now() + timedelta(minutes=30),
            lead_time_minutes=15,
            reminder_type="email",
            is_active=True
        )
        db_session.add(reminder)
        db_session.commit()
        
        # Verify default values for new fields
        assert reminder.status == 'pending'
        assert reminder.notification_method == 'in-app'
        assert reminder.delivery_attempted_at is None
        assert reminder.delivery_succeeded_at is None
        assert reminder.failure_reason is None
        assert reminder.reminder_metadata is None
    
    def test_create_reminder_with_explicit_new_field_values(self, db_session):
        """Test creating a reminder setting with explicit values for all new fields."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        event = Events(
            user_id=user.id,
            title="Test Event",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1)
        )
        db_session.add(event)
        db_session.commit()
        
        attempted_at = datetime.now() - timedelta(minutes=5)
        succeeded_at = datetime.now() - timedelta(minutes=4)
        test_metadata = {
            "retry_count": 2,
            "channel_config": {"email_template": "urgent", "priority": "high"},
            "user_preferences": ["no_weekend", "business_hours_only"]
        }
        
        reminder = ReminderSettings(
            user_id=user.id,
            event_id=event.id,
            reminder_time=datetime.now() + timedelta(minutes=30),
            lead_time_minutes=15,
            reminder_type="email",
            is_active=True,
            status='delivered',
            notification_method='email',
            delivery_attempted_at=attempted_at,
            delivery_succeeded_at=succeeded_at,
            failure_reason=None,
            reminder_metadata=test_metadata
        )
        db_session.add(reminder)
        db_session.commit()
        
        # Verify explicit values for new fields
        assert reminder.status == 'delivered'
        assert reminder.notification_method == 'email'
        assert reminder.delivery_attempted_at == attempted_at
        assert reminder.delivery_succeeded_at == succeeded_at
        assert reminder.failure_reason is None
        assert reminder.reminder_metadata == test_metadata
    
    def test_status_field_variations(self, db_session):
        """Test different status values (enum-like: 'pending', 'scheduled', 'delivered', 'cancelled', 'failed')."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        statuses = ['pending', 'scheduled', 'delivered', 'cancelled', 'failed']
        
        for i, status in enumerate(statuses):
            event = Events(
                user_id=user.id,
                title=f"Event {i}",
                start_time=datetime.now() + timedelta(hours=i),
                end_time=datetime.now() + timedelta(hours=i+1)
            )
            db_session.add(event)
            db_session.commit()
            
            reminder = ReminderSettings(
                user_id=user.id,
                event_id=event.id,
                reminder_time=datetime.now() + timedelta(minutes=30+i),
                lead_time_minutes=15,
                reminder_type="email",
                status=status
            )
            db_session.add(reminder)
            db_session.commit()
            
            assert reminder.status == status
    
    def test_notification_method_variations(self, db_session):
        """Test different notification method values (enum-like: 'email', 'push', 'in-app')."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        methods = ['email', 'push', 'in-app']
        
        for i, method in enumerate(methods):
            event = Events(
                user_id=user.id,
                title=f"Event {i}",
                start_time=datetime.now() + timedelta(hours=i),
                end_time=datetime.now() + timedelta(hours=i+1)
            )
            db_session.add(event)
            db_session.commit()
            
            reminder = ReminderSettings(
                user_id=user.id,
                event_id=event.id,
                reminder_time=datetime.now() + timedelta(minutes=30+i),
                lead_time_minutes=15,
                reminder_type="email",
                notification_method=method
            )
            db_session.add(reminder)
            db_session.commit()
            
            assert reminder.notification_method == method
    
    def test_delivery_timestamp_fields(self, db_session):
        """Test delivery_attempted_at and delivery_succeeded_at timestamp fields."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        event = Events(
            user_id=user.id,
            title="Test Event",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1)
        )
        db_session.add(event)
        db_session.commit()
        
        # Test both fields can be None
        reminder = ReminderSettings(
            user_id=user.id,
            event_id=event.id,
            reminder_time=datetime.now() + timedelta(minutes=30),
            lead_time_minutes=15,
            reminder_type="email"
        )
        db_session.add(reminder)
        db_session.commit()
        
        assert reminder.delivery_attempted_at is None
        assert reminder.delivery_succeeded_at is None
        
        # Test setting delivery_attempted_at without delivery_succeeded_at (failed attempt)
        attempted_time = datetime.now() - timedelta(minutes=10)
        reminder.delivery_attempted_at = attempted_time
        reminder.status = 'failed'
        reminder.failure_reason = 'Network timeout'
        db_session.commit()
        
        db_session.refresh(reminder)
        assert reminder.delivery_attempted_at == attempted_time
        assert reminder.delivery_succeeded_at is None
        assert reminder.status == 'failed'
        assert reminder.failure_reason == 'Network timeout'
        
        # Test setting both timestamps (successful delivery)
        succeeded_time = datetime.now() - timedelta(minutes=8)
        reminder.delivery_succeeded_at = succeeded_time
        reminder.status = 'delivered'
        reminder.failure_reason = None
        db_session.commit()
        
        db_session.refresh(reminder)
        assert reminder.delivery_attempted_at == attempted_time
        assert reminder.delivery_succeeded_at == succeeded_time
        assert reminder.status == 'delivered'
        assert reminder.failure_reason is None
    
    def test_failure_reason_field(self, db_session):
        """Test failure_reason text field for storing error messages."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        event = Events(
            user_id=user.id,
            title="Test Event",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1)
        )
        db_session.add(event)
        db_session.commit()
        
        failure_reasons = [
            "Network timeout after 30 seconds",
            "Invalid email address format",
            "User has disabled email notifications",
            "Rate limit exceeded - will retry in 1 hour",
            "SMTP server temporarily unavailable"
        ]
        
        for i, reason in enumerate(failure_reasons):
            reminder = ReminderSettings(
                user_id=user.id,
                event_id=event.id,
                reminder_time=datetime.now() + timedelta(minutes=30+i),
                lead_time_minutes=15,
                reminder_type="email",
                status='failed',
                delivery_attempted_at=datetime.now() - timedelta(minutes=5),
                failure_reason=reason
            )
            db_session.add(reminder)
            db_session.commit()
            
            assert reminder.failure_reason == reason
    
    def test_reminder_metadata_json_field(self, db_session):
        """Test reminder_metadata JSON field for storing flexible configuration."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        event = Events(
            user_id=user.id,
            title="Test Event",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1)
        )
        db_session.add(event)
        db_session.commit()
        
        # Test with comprehensive metadata
        complex_metadata = {
            "retry_config": {
                "max_retries": 3,
                "backoff_strategy": "exponential",
                "retry_intervals": [5, 15, 30]  # minutes
            },
            "notification_preferences": {
                "include_location": True,
                "include_attachments": False,
                "priority_level": "high",
                "custom_message": "Don't forget your presentation materials!"
            },
            "tracking_data": {
                "campaign_id": "weekly_standup_2024",
                "user_segment": "power_users",
                "ab_test_variant": "variant_b"
            },
            "delivery_stats": {
                "previous_attempts": 0,
                "success_rate": 0.95,
                "avg_delivery_time_seconds": 2.3
            },
            "flags": {
                "is_recurring_reminder": True,
                "requires_confirmation": False,
                "send_to_mobile_only": False
            }
        }
        
        reminder = ReminderSettings(
            user_id=user.id,
            event_id=event.id,
            reminder_time=datetime.now() + timedelta(minutes=30),
            lead_time_minutes=15,
            reminder_type="email",
            reminder_metadata=complex_metadata
        )
        db_session.add(reminder)
        db_session.commit()
        
        # Verify metadata is stored correctly
        assert reminder.reminder_metadata == complex_metadata
        
        # Test accessing nested values
        assert reminder.reminder_metadata["retry_config"]["max_retries"] == 3
        assert reminder.reminder_metadata["notification_preferences"]["priority_level"] == "high"
        assert reminder.reminder_metadata["flags"]["is_recurring_reminder"] == True
        
        # Test refreshing from database
        db_session.refresh(reminder)
        assert reminder.reminder_metadata == complex_metadata
    
    def test_reminder_metadata_update(self, db_session):
        """Test updating reminder_metadata on existing reminders."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        event = Events(
            user_id=user.id,
            title="Test Event",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1)
        )
        db_session.add(event)
        db_session.commit()
        
        # Create reminder with initial metadata
        initial_metadata = {"attempt": 1, "status": "initial"}
        reminder = ReminderSettings(
            user_id=user.id,
            event_id=event.id,
            reminder_time=datetime.now() + timedelta(minutes=30),
            lead_time_minutes=15,
            reminder_type="email",
            reminder_metadata=initial_metadata
        )
        db_session.add(reminder)
        db_session.commit()
        
        # Update metadata
        updated_metadata = {
            "attempt": 2,
            "status": "retry", 
            "last_error": "timeout",
            "next_retry_at": "2024-12-20T10:30:00Z"
        }
        reminder.reminder_metadata = updated_metadata
        db_session.commit()
        
        # Verify update
        db_session.refresh(reminder)
        assert reminder.reminder_metadata == updated_metadata
        assert reminder.reminder_metadata["attempt"] == 2
        assert reminder.reminder_metadata["status"] == "retry"
        assert reminder.reminder_metadata["last_error"] == "timeout"
    
    def test_status_index_functionality(self, db_session):
        """Test that the status field index works for efficient querying."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        # Create multiple reminders with different statuses
        statuses = ['pending'] * 5 + ['delivered'] * 3 + ['failed'] * 2
        reminders = []
        
        for i, status in enumerate(statuses):
            event = Events(
                user_id=user.id,
                title=f"Event {i}",
                start_time=datetime.now() + timedelta(hours=i),
                end_time=datetime.now() + timedelta(hours=i+1)
            )
            db_session.add(event)
            db_session.commit()
            
            reminder = ReminderSettings(
                user_id=user.id,
                event_id=event.id,
                reminder_time=datetime.now() + timedelta(minutes=30+i),
                lead_time_minutes=15,
                reminder_type="email",
                status=status
            )
            db_session.add(reminder)
            reminders.append(reminder)
        
        db_session.commit()
        
        # Query by status (this should use the index)
        pending_reminders = db_session.query(ReminderSettings).filter(
            ReminderSettings.status == 'pending'
        ).all()
        
        delivered_reminders = db_session.query(ReminderSettings).filter(
            ReminderSettings.status == 'delivered'
        ).all()
        
        failed_reminders = db_session.query(ReminderSettings).filter(
            ReminderSettings.status == 'failed'
        ).all()
        
        # Verify query results
        assert len(pending_reminders) == 5
        assert len(delivered_reminders) == 3
        assert len(failed_reminders) == 2
        
        # Verify all returned reminders have correct status
        for reminder in pending_reminders:
            assert reminder.status == 'pending'
        for reminder in delivered_reminders:
            assert reminder.status == 'delivered'
        for reminder in failed_reminders:
            assert reminder.status == 'failed'
    
    def test_complete_reminder_lifecycle(self, db_session):
        """Test a complete reminder lifecycle from pending to delivered."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        event = Events(
            user_id=user.id,
            title="Important Meeting",
            start_time=datetime.now() + timedelta(hours=2),
            end_time=datetime.now() + timedelta(hours=3)
        )
        db_session.add(event)
        db_session.commit()
        
        # Step 1: Create pending reminder
        reminder = ReminderSettings(
            user_id=user.id,
            event_id=event.id,
            reminder_time=datetime.now() + timedelta(hours=1, minutes=45),
            lead_time_minutes=15,
            reminder_type="email",
            status='pending',
            notification_method='email',
            reminder_metadata={
                "priority": "high",
                "template": "meeting_reminder"
            }
        )
        db_session.add(reminder)
        db_session.commit()
        
        # Verify initial state
        assert reminder.status == 'pending'
        assert reminder.delivery_attempted_at is None
        assert reminder.delivery_succeeded_at is None
        assert reminder.failure_reason is None
        
        # Step 2: Mark as scheduled
        reminder.status = 'scheduled'
        reminder.reminder_metadata = {
            **reminder.reminder_metadata,
            "scheduled_at": "2024-12-19T09:45:00Z",
            "job_id": "job_12345"
        }
        db_session.commit()
        
        assert reminder.status == 'scheduled'
        
        # Step 3: Record delivery attempt
        attempt_time = datetime.now() - timedelta(minutes=2)
        reminder.delivery_attempted_at = attempt_time
        reminder.status = 'delivered'
        db_session.commit()
        
        assert reminder.delivery_attempted_at == attempt_time
        assert reminder.status == 'delivered'
        
        # Step 4: Record successful delivery
        success_time = datetime.now() - timedelta(minutes=1)
        reminder.delivery_succeeded_at = success_time
        reminder.reminder_metadata = {
            **reminder.reminder_metadata,
            "delivery_confirmed_at": "2024-12-19T10:48:00Z",
            "recipient_opened": True,
            "delivery_latency_ms": 1250
        }
        db_session.commit()
        
        # Final verification
        db_session.refresh(reminder)
        assert reminder.status == 'delivered'
        assert reminder.delivery_attempted_at == attempt_time
        assert reminder.delivery_succeeded_at == success_time
        assert reminder.failure_reason is None
        assert reminder.reminder_metadata["delivery_confirmed_at"] == "2024-12-19T10:48:00Z"
        assert reminder.reminder_metadata["recipient_opened"] == True
        assert reminder.reminder_metadata["delivery_latency_ms"] == 1250
        
    def test_reminder_repr_includes_new_fields(self, db_session):
        """Test that the string representation includes the new status field."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        reminder = ReminderSettings(
            user_id=user.id,
            reminder_time=datetime.now() + timedelta(minutes=30),
            lead_time_minutes=15,
            reminder_type="email",
            status='scheduled'
        )
        db_session.add(reminder)
        db_session.commit()
        
        repr_str = repr(reminder)
        assert "ReminderSettings" in repr_str
        assert "status='scheduled'" in repr_str
        assert "reminder_type='email'" in repr_str
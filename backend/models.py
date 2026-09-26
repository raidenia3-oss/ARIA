from sqlalchemy import Column, Integer, String, Float, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(String, default="user")


class ServiceStatus(Base):
    __tablename__ = "service_status"

    id = Column(Integer, primary_key=True, index=True)
    service = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, nullable=False)
    updated_at = Column(Float, nullable=False)


class LogEntry(Base):
    __tablename__ = "log_entries"

    id = Column(Integer, primary_key=True, index=True)
    service = Column(String, index=True, nullable=False)
    level = Column(String, default="INFO")
    message = Column(Text, nullable=False)
    timestamp = Column(Float, nullable=False)


class TrainingJob(Base):
    __tablename__ = "training_jobs"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, default="idle")
    model_name = Column(String)
    dataset_path = Column(String)
    output_dir = Column(String)
    started_at = Column(Float, nullable=True)
    finished_at = Column(Float, nullable=True)
    metrics = Column(Text, nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(String, index=True, nullable=True)
    created_at = Column(Float, nullable=False)
    updated_at = Column(Float, nullable=False)
    extra = Column(Text, nullable=True)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    provider = Column(String, nullable=True)
    timestamp = Column(Float, nullable=False)
    extra = Column(Text, nullable=True)


class SystemPrompt(Base):
    __tablename__ = "system_prompts"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    updated_at = Column(Float, nullable=False)


class Story(Base):
    __tablename__ = "stories"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    premise = Column(Text, nullable=True)
    tone = Column(String, default="dramatic")
    characters = Column(Text, nullable=True)
    world_rules = Column(Text, nullable=True)
    created_at = Column(Float, nullable=False)
    updated_at = Column(Float, nullable=False)


class StoryScene(Base):
    __tablename__ = "story_scenes"

    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("stories.id"), nullable=False)
    text = Column(Text, nullable=False)
    characters_present = Column(Text, nullable=True)
    timestamp = Column(Float, nullable=False)


class FanficDraft(Base):
    __tablename__ = "fanfic_drafts"

    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("stories.id"), nullable=False)
    title = Column(String, nullable=False)
    platform = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(Float, nullable=False)
    updated_at = Column(Float, nullable=False)


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, index=True, nullable=False)
    timestamp = Column(Float, nullable=False, index=True)
    module = Column(String, index=True, nullable=False)
    data = Column(Text, nullable=False)
    extra = Column(Text, nullable=True)


class Anomaly(Base):
    __tablename__ = "analytics_anomalies"

    id = Column(Integer, primary_key=True, index=True)
    metric = Column(String, nullable=False)
    current_value = Column(Float, nullable=False)
    expected_range = Column(Text, nullable=True)
    severity = Column(String, nullable=False)
    timestamp = Column(Float, nullable=False)


class MetricSnapshot(Base):
    __tablename__ = "analytics_metric_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    period = Column(String, nullable=False)
    metrics = Column(Text, nullable=False)
    created_at = Column(Float, nullable=False)


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key_id = Column(String, unique=True, index=True, nullable=False)
    key_hash = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(String, index=True, nullable=False)
    created_at = Column(Float, nullable=False)
    last_used = Column(Float, nullable=True)
    expires_at = Column(Float, nullable=True)
    permissions = Column(Text, nullable=False)
    rate_limit = Column(Integer, default=1000)
    is_active = Column(Boolean, default=True)


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, index=True, nullable=False)
    timestamp = Column(Float, nullable=False, index=True)
    ip_address = Column(String, index=True, nullable=False)
    user_id = Column(String, index=True, nullable=True)
    endpoint = Column(String, nullable=False)
    status = Column(String, nullable=False)
    reason = Column(Text, nullable=True)
    severity = Column(String, nullable=False)


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, unique=True, index=True, nullable=False)
    device_type = Column(String, index=True, nullable=False)
    device_name = Column(String, nullable=False)
    ip_address = Column(String, index=True, nullable=False)
    cpu_cores = Column(Integer, nullable=False)
    ram_gb = Column(Float, nullable=False)
    gpu_available = Column(Boolean, default=False)
    capabilities = Column(Text, nullable=False)
    is_online = Column(Boolean, default=True)
    last_heartbeat = Column(Float, nullable=False)
    load_percent = Column(Float, nullable=False)
    battery_percent = Column(Float, nullable=True)
    bandwidth_mbps = Column(Float, nullable=False)
    uptime_seconds = Column(Integer, nullable=False)
    version = Column(String, nullable=False)


class DistributedTask(Base):
    __tablename__ = "distributed_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, index=True, nullable=False)
    task_type = Column(String, index=True, nullable=False)
    priority = Column(Integer, nullable=False)
    required_capability = Column(String, nullable=False)
    status = Column(String, index=True, nullable=False)
    assigned_device = Column(String, nullable=True)
    created_at = Column(Float, nullable=False)
    started_at = Column(Float, nullable=True)
    completed_at = Column(Float, nullable=True)
    result = Column(Text, nullable=True)
    payload = Column(Text, nullable=False)


class GeneratedApp(Base):
    __tablename__ = "generated_apps"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(String, unique=True, index=True, nullable=False)
    app_name = Column(String, index=True, nullable=False)
    app_type = Column(String, index=True, nullable=False)
    path = Column(String, nullable=False)
    config = Column(Text, nullable=False)
    created_at = Column(Float, nullable=False)
    updated_at = Column(Float, nullable=False)


class ModelMetadata(Base):
    __tablename__ = "model_metadata"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String, unique=True, index=True, nullable=False)
    model_type = Column(String, index=True, nullable=False)
    base_model = Column(String, nullable=False)
    version = Column(String, nullable=False)
    created_at = Column(Float, nullable=False)
    trained_at = Column(Float, nullable=True)
    genre = Column(String, nullable=True)
    language = Column(String, nullable=True)
    accuracy = Column(Float, default=0.0)
    perplexity = Column(Float, nullable=True)
    parameters = Column(Integer, nullable=False)
    quantization = Column(String, nullable=True)
    hardware_used = Column(String, nullable=False)
    training_time_hours = Column(Float, default=0.0)
    file_size_mb = Column(Float, nullable=False)
    is_active = Column(Boolean, default=False)
    performance_metrics = Column(Text, nullable=True)
    lora_rank = Column(Integer, nullable=True)
    lora_alpha = Column(Integer, nullable=True)


class ABTest(Base):
    __tablename__ = "ab_tests"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(String, unique=True, index=True, nullable=False)
    model_a = Column(String, nullable=False)
    model_b = Column(String, nullable=False)
    metric = Column(String, nullable=False)
    start_date = Column(Float, nullable=False)
    end_date = Column(Float, nullable=True)
    sample_size = Column(Integer, nullable=False)
    traffic_split = Column(Float, default=0.5)
    results_a = Column(Text, nullable=True)
    results_b = Column(Text, nullable=True)
    winner = Column(String, nullable=True)
    confidence = Column(Float, default=0.0)
    status = Column(String, index=True, nullable=False)


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    genre = Column(String, nullable=True)
    language = Column(String, nullable=True)
    stories_count = Column(Integer, default=0)
    path = Column(String, nullable=False)
    created_at = Column(Float, nullable=False)
    updated_at = Column(Float, nullable=False)


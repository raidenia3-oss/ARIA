from backend.agents.kilo_bridge import KiloBridge, KiloTask, kilo_bridge
from backend.agents.react_loop import ReactLoop
from backend.agents.orchestrator import (
    AgentTask,
    ReasoningStep,
    TaskStatus,
    ToolConnector,
    ToolResult,
    ToolResultStatus,
    VibeCodingOrchestrator,
    get_orchestrator,
    reset_orchestrator,
    vibe_orchestrator,
)
from backend.agents.tools_registry import (
    DynamicToolRegistry,
    SkillExecutionSandbox,
    ToolEntry,
    get_tools_registry,
    reset_tools_registry,
    tool_registry,
)
from backend.agents.tools_routes import router as tools_registry_router
from backend.agents.agent_autoconfigurator import (
    AgentAutoConfigurator,
    AgentMetrics,
    ImprovementAction,
    ImprovementPlan,
)
from backend.agents.agent_newsletter import NewsletterAgent, newsletter_agent
from backend.agents.agent_social_media import SocialMediaAgent, social_agent
from backend.agents.agent_analytics import AnalyticsAgent, analytics_agent
from backend.agents.agent_code_reviewer import (
    CodeReviewerAgent,
    code_reviewer,
)
from backend.agents.agent_video_analyzer import (
    VideoAnalyzerAgent,
    video_analyzer,
)
from backend.agents.agent_image_processor import (
    ImageProcessorAgent,
    image_processor,
)
from backend.agents.agent_data_scientist import (
    DataScientistAgent,
    data_scientist,
)
from backend.agents.agent_language_tutor import (
    LanguageTutorAgent,
    language_tutor,
)
from backend.agents.agent_fitness_coach import (
    FitnessCoachAgent,
    fitness_coach,
)
from backend.agents.agent_music_composer import (
    MusicComposerAgent,
    music_composer,
)
from backend.agents.agent_psychology_counselor import (
    PsychologyCounselorAgent,
    psychology_counselor,
)
from backend.agents.agent_business_analyst import (
    BusinessAnalystAgent,
    business_analyst,
)
from backend.agents.agent_researcher import (
    ResearcherAgent,
    researcher,
)

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)

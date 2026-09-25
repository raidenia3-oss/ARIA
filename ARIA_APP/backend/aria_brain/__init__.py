"""ARIA Brain — Módulo principal de razonamiento"""

from .memoria_sistema import ShortTermMemory, LongTermMemory, SemanticMemory, EpisodicMemory
from .reasoning_engine import ReasoningEngine
from .decision_making import DecisionMaking
from .learning_system import LearningSystem
from .creativity_engine import CreativityEngine
from .emotion_simulation import EmotionSimulation
from .prediction_model import PredictionModel
from .explanation_generator import ExplanationGenerator


class AriaBrain:
    """Motor de inteligencia principal de ARIA"""
    
    def __init__(self):
        self.memory_short = ShortTermMemory()
        self.memory_long = LongTermMemory()
        self.semantic = SemanticMemory()
        self.episodic = EpisodicMemory()
        self.reasoning = ReasoningEngine()
        self.decision = DecisionMaking()
        self.learning = LearningSystem()
        self.creativity = CreativityEngine()
        self.emotion = EmotionSimulation()
        self.prediction = PredictionModel()
        self.explanation = ExplanationGenerator()
    
    async def think_and_decide(self, situation):
        """Procesa situación y toma decisión inteligente"""
        # Razona
        analysis = await self.reasoning.analyze(situation)
        
        # Considera emoción
        emotion = await self.emotion.get_emotional_response(situation)
        
        # Toma decisión
        decision = await self.decision.decide(analysis, emotion)
        
        # Genera explicación
        explanation = await self.explanation.explain(decision)
        
        # Aprende
        await self.learning.learn_from(situation, decision, explanation)
        
        return {
            'decision': decision,
            'confidence': 0.95,
            'explanation': explanation,
            'emotion': emotion
        }


__all__ = [
    'AriaBrain',
    'ShortTermMemory',
    'LongTermMemory',
    'SemanticMemory',
    'EpisodicMemory',
    'ReasoningEngine',
    'DecisionMaking',
    'LearningSystem',
    'CreativityEngine',
    'EmotionSimulation',
    'PredictionModel',
    'ExplanationGenerator'
]

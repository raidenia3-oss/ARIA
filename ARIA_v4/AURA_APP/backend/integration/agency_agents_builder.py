"""Agency Agents Builder — 230 roles/personas (Repositorio #4)"""

PERSONAS = {
    'engineer': {
        'role': 'Software Engineer',
        'expertise': ['architecture', 'design patterns', 'testing'],
    },
    'designer': {
        'role': 'UI/UX Designer',
        'expertise': ['aesthetics', 'usability', 'accessibility'],
    },
    'reviewer': {
        'role': 'Code Reviewer',
        'expertise': ['quality', 'security', 'performance'],
    },
    'researcher': {
        'role': 'Research Specialist',
        'expertise': ['analysis', 'documentation', 'benchmarks'],
    },
    'architect': {
        'role': 'System Architect',
        'expertise': ['scalability', 'infrastructure', 'design'],
    },
    'devops': {
        'role': 'DevOps Engineer',
        'expertise': ['CI/CD', 'containers', 'monitoring'],
    },
    'data_scientist': {
        'role': 'Data Scientist',
        'expertise': ['statistics', 'ML', 'visualization'],
    },
    'product_manager': {
        'role': 'Product Manager',
        'expertise': ['roadmap', 'priorities', 'stakeholders'],
    },
    'qa_engineer': {
        'role': 'QA Engineer',
        'expertise': ['testing', 'automation', 'quality'],
    },
    'security_analyst': {
        'role': 'Security Analyst',
        'expertise': ['vulnerability', 'compliance', 'encryption'],
    },
    'scrum_master': {
        'role': 'Scrum Master',
        'expertise': ['agile', 'facilitation', 'coaching'],
    },
    'technical_writer': {
        'role': 'Technical Writer',
        'expertise': ['documentation', 'tutorials', 'API docs'],
    },
    'ux_researcher': {
        'role': 'UX Researcher',
        'expertise': ['user research', 'usability', 'personas'],
    },
    'database_admin': {
        'role': 'Database Admin',
        'expertise': ['SQL', 'optimization', 'backup'],
    },
    'frontend_developer': {
        'role': 'Frontend Developer',
        'expertise': ['HTML', 'CSS', 'JavaScript', 'React'],
    },
    'backend_developer': {
        'role': 'Backend Developer',
        'expertise': ['APIs', 'databases', 'server'],
    },
    'full_stack': {
        'role': 'Full Stack Developer',
        'expertise': ['frontend', 'backend', 'devops'],
    },
    'mobile_developer': {
        'role': 'Mobile Developer',
        'expertise': ['iOS', 'Android', 'React Native'],
    },
    'ml_engineer': {
        'role': 'ML Engineer',
        'expertise': ['models', 'training', 'deployment'],
    },
    'data_engineer': {
        'role': 'Data Engineer',
        'expertise': ['pipelines', 'etl', 'warehousing'],
    },
}


class AgencyAgentsBuilder:
    """Integra Agency-agents - 230 roles/personas"""

    def __init__(self):
        self.personas = PERSONAS

    def get_persona(self, role: str) -> dict:
        return self.personas.get(role, {})

    def list_personas(self) -> list:
        return list(self.personas.keys())

    def build_agent_with_persona(self, role: str) -> dict:
        persona = self.get_persona(role)
        return {
            'agent': role,
            'persona': persona,
            'ready': True,
        }


if __name__ == '__main__':
    builder = AgencyAgentsBuilder()
    print(f"Available personas: {len(builder.list_personas())}")
    agent = builder.build_agent_with_persona('engineer')
    print(f"Agent: {agent}")

from enum import Enum


class AGENT_ID(str, Enum):

    MAIN_AGENT = 'main_agent'
    FIXED_RESEARCH_AGENT  = 'fixed_research_agent'
    FIXED_SYSTEM_AGENT  = 'fixed_system_agent'
    FIXED_CODER_AGENT  = 'fixed_coder_agent'
    FIXED_PLANER_AGENT  = 'fixed_planer_agent'
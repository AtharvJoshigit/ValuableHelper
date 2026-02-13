
from agents import main_agent, coder_agent, plan_manager_agent, research_agent, system_operator_agent

class ALLFixedAgents:


    def start() : 

        main_agent.MainAgent().start()
        coder_agent.CoderAgent().start()
        system_operator_agent.SystemOperatorAgent().start()
        plan_manager_agent.PlanManagerAgent().start()
        research_agent.ResearchAgent().start()

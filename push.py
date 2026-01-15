from nanocode_dspy import AgentProgram, AgentConfig

agent = AgentProgram(AgentConfig())
agent.push_to_hub("farouk1/nanocode-dspy", with_code=True)
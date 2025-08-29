class LLMToolParameter(object):
	def __init__(self, name, description, par_type = None, enum=None, required=None):
		self.name = name
		self.type = par_type
		self.description = description
		self.enum = enum
		self.required = required
	def get_model_content(self):
		ret = {"description":self.description, "type":self.type or "string"}
		if self.enum:
			ret["enum"] = self.enum
		
		return self.name, ret, self.required

class LLMTool(object):
	def __init__(self, name, description, parameters=None, master_state=None):
		self.name = name
		self.description = description
		self.parameters = parameters or []
		self.master_state = master_state

	def can_invoke(self):
		return True

	async def invoke(self, args, master_state):
		return "OK"

	def get_model_function_call_metadata(self):
		props = {}
		required = []
		for parameter in self.parameters:
			prop_key, prop_value, is_required = parameter.get_model_content()
			props[prop_key] = prop_value
			if is_required:
				required.append(prop_key)

		ret = {
				"type": "function",
				"name": self.name,
				"description":self.description,
		 		"parameters":{"type":"object","properties":props,"required":required}
				}
		return ret


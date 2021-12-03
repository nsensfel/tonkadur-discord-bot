import copy
import json
import math
import random

class Tonkadur:
    def generate_instance_of (self, typedef):
        if (typedef['category'] == "bool"):
            return False
        elif (typedef['category'] == "float"):
            return 0.0
        elif (typedef['category'] == "int"):
            return 0
        elif (typedef['category'] == "text"):
            result = dict()
            result['content'] = []
            result['effect'] = None
            return result
        elif (typedef['category'] == "string"):
            return ""
        elif (typedef['category'] == "list"):
            return dict()
        elif (typedef['category'] == "pointer"):
            return []
        elif (typedef['category'] == "structure"):
            if (typedef['name'] == "wild dict"):
                return dict()
            else:
                return copy.deepcopy(self.types[typedef['name']])

    def __init__ (self, json_file):
        self.memory = dict()
        self.types = dict()
        self.sequences = dict()
        self.code = []
        self.program_counter = 0
        self.allocated_data = 0
        self.last_choice_index = -1
        self.available_options = []
        self.memorized_target = []
        self.last_user = ("", "")

        with open(json_file, 'r') as f:
            json_content = json.load(f)

            #### INITIALIZE TYPES ##############################################
            for typedef in json_content['structure_types']:
                new_type = dict()

                for field in typedef['fields']:
                    new_type[field['name']] = self.generate_instance_of(field['type'])

                self.types[typedef['name']] = new_type

            #### INITIALIZE SEQUENCES ##########################################
            for seqdef in json_content['sequences']:
                self.sequences[seqdef['name']] = seqdef['line']

            #### INITIALIZE CODE ###############################################
            self.code = json_content['code']


    def compute (self, computation):
        computation_category = computation['category']

        if (computation_category == "add_text_effect"):
            effect = dict()
            effect['name'] = computation['effect']
            effect['parameters'] = []

            for c in computation['parameters']:
                effect['parameters'].append(self.compute(c))

            result = dict()
            result['content'] = []
            result['effect'] = effect

            for c in computation['content']:
                result['content'].append(self.compute(c))

            return result
        elif (computation_category == "cast"):
            origin_type = computation['from']['category']
            target_type = computation['to']['category']
            content = self.compute(computation['content'])

            if (target_type == "string"):
                if (origin_type == "bool"):
                    # Python would return True and False by default.
                    return "true" if content else "false"
                else:
                    return str(content)
            elif (target_type == "float"):
                return float(content)
            elif (target_type == "bool"):
                if (origin_type == "string"):
                    return (content == "true")
                elif (origin_type == "int"):
                    return (content != 0)
            elif (target_type == "int"):
                if (origin_type == "float"):
                    return math.floor(content)
                else:
                    return int(content)
        elif (computation_category == "constant"):
            target_type = computation['type']['category']
            content = computation['value']

            if (target_type == "string"):
                return content
            elif (target_type == "float"):
                return float(content)
            elif (target_type == "bool"):
                return (content == "true")
            elif (target_type == "int"):
                return int(content)
            else:
                print("Unknown Constant type '" + str(target_type) + "'")
                raise "error"
        elif (computation_category == "if_else"):
            cond = self.compute(computation['condition'])

            if (cond):
                return self.compute(computation['if_true'])
            else:
                return self.compute(computation['if_false'])
        elif (computation_category == "new"):
            address = ".alloc." + str(self.allocated_data)
            self.allocated_data += 1
            self.memory[address] = self.generate_instance_of(computation['target'])
            #print("Allocated " + str(address) + " = " + str(self.memory[address]))

            return [address]
        elif (computation_category == "operation"):
            operator = computation['operator']
            x = self.compute(computation['x'])
            y = self.compute(computation['y']) if ('y' in computation) else None
            if (operator == "divide"):
                if (isinstance(x, int)):
                    return x // y
                else:
                    return x / y
            elif (operator == "minus"):
                return x - y
            elif (operator == "modulo"):
                return x % y
            elif (operator == "plus"):
                return x + y
            elif (operator == "power"):
                return x ** y
            elif (operator == "rand"):
                return random.randint(x, y)
            elif (operator == "times"):
                return x * y
            elif (operator == "and"):
                return x and y
            elif (operator == "not"):
                return not x
            elif (operator == "less_than"):
                return x < y
            elif (operator == "equals"):
                return x == y
            else:
                print("unknown operator " + operator)

        elif (computation_category == "address"):
            result = self.compute(computation['address'])
            if (isinstance(result, list)):
                return result
            else:
                return [result]
        elif (computation_category == "relative_address"):
            base = self.compute(computation['base']).copy()
            base.append(self.compute(computation['extra']))
            return base
        elif (computation_category == "text"):
            result = dict()
            result['effect'] = None
            result['content'] = []
            for c in computation['content']:
                cc = self.compute(c)

                if (
                    (type(cc) is dict)
                    and ('effect' in cc)
                    and cc['effect'] == None
                ):
                    result['content'].extend(cc['content'])
                else:
                    result['content'].append(cc)

            return result
        elif (computation_category == "newline"):
            result = dict()
            result['effect'] = None
            result['content'] = ['\n']

            return result
        elif (computation_category == "extra_computation"):
            print("[E] Unhandled extra computation " + str(computation))

            return None
        elif (computation_category == "size"):
            target = self.memory
            access = self.compute(computation['reference'])

            for addr in access:
                if (not (addr in target)):
                    return 0
                else:
                    target = target[addr]

            return len(target)
        elif (computation_category == "value_of"):
            target = self.memory
            access = self.compute(computation['reference'])
            #print("(value_of " + str(access) + ")")
            for addr in access:
                #print("Reading " + str(addr) + " of " + str(target))
                #print("addr = " + str(addr))
                target = target[addr]
               # if (isinstance(target, list)):
               #     print("That's a list.")
            return target
        elif (computation_category == "last_choice_index"):
            return self.last_choice_index
        else:
            print("Unknown Wyrd computation: \"" + computation_category + "\"")

    def resolve_choice_to (self, index, user_name, user_id):
        self.available_options = []
        self.last_choice_index = index
        self.last_user = (user_name, user_id)

    def store_integer (self, value, user_name, user_id):
        current_val = self.memory
        self.last_user = (user_name, user_id)

        for access in self.memorized_target:
            pre_val = current_val
            last_access = access
            if (access in current_val):
                current_val = current_val[access]

        pre_val[last_access] = value

    def store_string (self, value, user_name, user_id):
        current_val = self.memory
        self.last_user = (user_name, user_id)

        for access in self.memorized_target:
            pre_val = current_val
            last_access = access
            if (access in current_val):
                current_val = current_val[access]

        pre_val[last_access] = value

    def run (self):
        while True:
            #print("\nmemory: " + str(self.memory))
            #print("\nline: " + str(self.program_counter))
            instruction = self.code[self.program_counter]
            instruction_category = instruction['category']
            #print("instruction:" + str(instruction))

            if (instruction_category == "add_text_option"):
                result = dict()
                result["category"] = "text_option"
                result["label"] = self.compute(instruction['label'])
                self.available_options.append(result)
                self.program_counter += 1
            elif (instruction_category == "add_event_option"):
                result = dict()
                result["category"] = "event_option"
                result["name"] = instruction["event"]
                params = []

                for param in instruction['parameters']:
                    params.append(self.compute(param))

                result["parameters"] = params
                self.available_options.append(result)
                self.program_counter += 1
            elif (instruction_category == "assert"):
                condition = self.compute(instruction['condition'])

                if (not condition):
                    result = dict()
                    result["category"] = "assert"
                    result["line"] = self.program_counter
                    result["message"] = self.compute(instruction['message'])
                    self.program_counter += 1
                    return result

                self.program_counter += 1
            elif (instruction_category == "display"):
                result = dict()
                result["category"] = "display"
                result["content"] = self.compute(instruction['content'])
                self.program_counter += 1

                return result
            elif (instruction_category == "end"):
                result = dict()
                result["category"] = "end"

                return result
            elif (instruction_category == "extra_instruction"):
                result = dict()
                result["category"] = "extra_instruction"
                result["name"] = instruction["name"]
                params = []

                for param in instruction['parameters']:
                    params.append(self.compute(param))

                result["parameters"] = params

                self.program_counter += 1

                print("[E] Unhandled extra instruction " + str(result))

                return result
            elif (instruction_category == "remove"):
                pre_val = self.memory
                current_val = pre_val
                last_access = ""

                for access in self.compute(instruction["reference"]):
                    pre_val = current_val
                    last_access = access
                    current_val = current_val[access]

                #print("Removing " + str(last_access) + " of " + str(pre_val))
                del pre_val[last_access]

                self.program_counter += 1
            elif (instruction_category == "resolve_choice"):
                result = dict()
                result["category"] = "resolve_choice"
                result["options"] = self.available_options
                self.program_counter += 1

                return result
            elif (instruction_category == "set_pc"):
                self.program_counter = self.compute(instruction["value"])
            elif (instruction_category == "set_value"):
                current_val = self.memory
                #print("Reference:" + str(instruction["reference"]))
                access_full = self.compute(instruction["reference"])
                #print("Writing: " + str(access_full))

                for access in access_full[:-1]:
                    current_val = current_val[access]

                result = self.compute(instruction["value"])

                if (isinstance(result, list) or isinstance(result, dict)):
                    result = copy.deepcopy(result)

                current_val[access_full[-1]] = result

                self.program_counter += 1
            elif (instruction_category == "initialize"):
                current_val = self.memory
                access_full = self.compute(instruction["reference"])

                for access in access_full[:-1]:
                    current_val = current_val[access]

                current_val[access_full[-1]] = self.generate_instance_of(instruction["type"])

                self.program_counter += 1
            elif (instruction_category == "prompt_integer"):
                result = dict()
                result["category"] = "prompt_integer"
                result["min"] = self.compute(instruction['min'])
                result["max"] = self.compute(instruction['max'])
                result["label"] = self.compute(instruction['label'])

                self.memorized_target = self.compute(instruction['target'])

                self.program_counter += 1

                return result

            elif (instruction_category == "prompt_string"):
                result = dict()
                result["category"] = "prompt_string"
                result["min"] = self.compute(instruction['min'])
                result["max"] = self.compute(instruction['max'])
                result["label"] = self.compute(instruction['label'])

                self.memorized_target = self.compute(instruction['target'])

                self.program_counter += 1

                return result
            else:
                print("Unknown Wyrd instruction: \"" + instruction_category + "\"")


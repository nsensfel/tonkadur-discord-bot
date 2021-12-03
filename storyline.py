import tonkadur

class Storyline:
    NOT_STARTED = -1
    WANTS_INT = 0
    WANTS_STR = 1
    WANTS_USER_CHOICE = 2
    IS_RUNNING = 3
    HAS_ENDED = 4

    def __init__ (self, filename):
        self.state = tonkadur.Tonkadur(filename)
        self.last_username = None
        self.last_user_id = None
        self.status = Storyline.NOT_STARTED
        self.next_input_min = 0
        self.next_input_max = 0
        self.text_options = []
        self.event_options = []
        self.output = ""

    def reset_next_input (self):
        self.next_input_type = None
        self.next_input_min = 0
        self.next_input_max = 0
        self.text_options = []
        self.event_options = []

    def handle_int_input (self, text, username, user_id):
        user_input = int(text)
        if (
            (user_input >= self.next_input_min)
            and (user_input <= self.next_input_max)
        ):
            self.state.store_integer(user_input, username, user_id)
            self.status = Storyline.IS_RUNNING
            self.run()
        else:
            self.display_string(
                "Integer should be within ["
                + str(self.next_input_min)
                + ", "
                + str(self.next_input_max)
                + "] range."
            )

    def handle_str_input (self, text, username, user_id):
        if (
            (len(text) >= self.next_input_min)
            and (len(text) <= self.next_input_max)
        ):
            self.status = Storyline.IS_RUNNING
            self.state.store_string(user_input, username, user_id)
            self.run()
        else:
            self.display_string(
                "String size should be within ["
                + str(self.next_input_min)
                + ", "
                + str(self.next_input_max)
                + "] range."
            )

    def handle_option_input (self, text, username, user_id):
        user_input = int(text)

        if (user_input < 0) or (user_input >= len(self.text_options)):
            self.display_string(
                "Invalid choice. Number between 0 and "
                + str(len(self.text_options) -1)
                + " expected."
            )
            return

        self.status = Storyline.IS_RUNNING
        self.state.resolve_choice_to(self.text_options[user_input], username, user_id)
        self.run()

    def handle_answer (self, text, username, user_id):
        self.last_username = username
        self.last_user_id = user_id

        if self.status == Storyline.NOT_STARTED:
            self.run()
        elif self.status == Storyline.WANTS_INT:
            self.handle_int_input(text, username, user_id)
        elif self.status == Storyline.WANTS_STR:
            return self.handle_str_input(text, username, user_id)
        elif self.status == Storyline.WANTS_USER_CHOICE:
            return self.handle_option_input(text, username, user_id)
        else:
            self.display_string("No input expected at this point.")

    def handle_event_input (self, event_name, event_data, username, user_id):
        if not (self.status == Storyline.WANTS_USER_CHOICE):
            print(
                "[W] Ignoring event \""
                + str(event_name)
                + "\" from "
                + str(username)
                + " ("
                + str(user_id)
                + "): not expecting a player choice."
            )
            return

        #for (expected_event_name, expected_event_data, option_id) in self.event_options:
        #    if (
        #        (expected_event_name == event_name)
        #        and (expected_event_data == event_data)
        #    ):
        # TODO: Event support.

    def text_to_string (text):
        str_content = ""

        if (not (text['effect'] is None)):
            str_content += "{(" + str(text['effect']) + ") "

        for c in text['content']:
            if (isinstance(c, str)):
                str_content += c
            else:
                str_content += Storyline.text_to_string(c)

        if (not (text['effect'] is None)):
            str_content += "}"

        return str_content


    def display_text (self, text):
        self.display_string(Storyline.text_to_string(text))

    def display_string (self, string):
        self.output += string

    def pop_output_string (self):
        result = self.output
        self.output = ""

        return result

    def has_output (self):
        return (len(self.output) > 0)

    def has_ended (self):
        return (self.status == Storyline.HAS_ENDED)

    def run (self):
        result = self.state.run()
        result_category = result['category']

        if (self.status == Storyline.NOT_STARTED):
            self.status = Storyline.IS_RUNNING

        if (result_category == "end"):
            self.status = Storyline.HAS_ENDED
        elif (result_category == "display"):
            self.display_text(result['content'])
            self.run()
        elif (result_category == "prompt_integer"):
            self.reset_next_input()
            self.status = Storyline.WANTS_INT
            self.next_input_min = result['min']
            self.next_input_max = result['max']
            self.display_text(result['label'])
            self.display_string(
                "\n(an integer between "
                + str(result['min'])
                + " and "
                + str(result['max'])
                + " is expected)\n"
            )
        elif (result_category == "prompt_string"):
            self.reset_next_input()
            self.status = Storyline.WANTS_STR
            self.next_input_min = result['min']
            self.next_input_max = result['max']
            self.display_text(result['label'])
            self.display_string(
                "\n(a string of size between "
                + str(result['min'])
                + " and "
                + str(result['max'])
                + " is expected)\n"
            )
        elif (result_category == "assert"):
            print(
                "Assert failed at line "
                + str(result['line'])
                + ":"
                + str(result['message'])
            )
            print(str(state.memory))
            self.display_string(
                "\nAssert failed at line "
                + str(result['line'])
                + ": "
            )
            self.display_text(result['message'])
            self.display_string(
                "\nState of memory:\n"
                + str(state.memory)
            )
            self.run()
        elif (result_category == "resolve_choice"):
            self.reset_next_input()
            self.status = Storyline.WANTS_USER_CHOICE
            current_choice = 0

            self.display_string("\n")

            for choice in result['options']:
                if (choice["category"] == "text_option"):
                    self.display_string(str(current_choice) + ": ")
                    self.display_text(choice['label'])
                    self.display_string("\n")
                    self.text_options.append(current_choice);
                else:
                    # TODO: handle events.
                    self.event_options.append(current_choice)
                current_choice += 1


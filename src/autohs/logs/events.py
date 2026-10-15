import copy

class LineInfoContainer:
    def __init__(self, line_type, **kwargs):
        self.line_type = line_type
        self.info_dict = copy.copy(kwargs)

    def __str__(self):
        res = "line_type: " + str(self.line_type) + "\n"
        if len(self.info_dict) > 0:
            res += "info_dict: {\n"
            for key, value in self.info_dict.items():
                res += "\t" + str(key) + ": " + str(value) + "\n"
            res += "}\n"
        return res


class LogInfoContainer:
    def __init__(self, log_type):
        self.log_type = log_type
        self.message_list = []

    def append_info(self, line_info):
        self.message_list.append(line_info)

    @property
    def length(self):
        return len(self.message_list)


def fetch_entity_id(input_string):
    if input_string[0] != "[":
        return input_string

    # 去除前后的 "[", "]"
    kv_list = input_string[1:-1]

    # 提取成形如 [... , "id=233" , ...]的格式
    kv_list = kv_list.split(" ")

    for item in kv_list:
        if item[:3] == "id=":
            return item[3:]


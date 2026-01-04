from copy import copy
import logging

def prompt_format(prompt, **kwargs):
    try:
        prompt = copy(prompt)
        for k in kwargs:
            rep = '{' + k + '}'
            # if prompt.txt.count(rep) > 1:
            #     raise Exception(f"Prompt有问题，{rep}出现多次")
            prompt = prompt.replace(rep, kwargs[k])
    except Exception as e:
        logging.error(f"Prompt格式化失败: {e}")
        print(prompt)
        print(kwargs)
        raise RuntimeError(e)
    return prompt
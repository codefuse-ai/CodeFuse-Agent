import json
import regex as re


class Post:
    @staticmethod
    def extract_pattern(text, pattern):
        pattern = re.compile(f'```{pattern}\s(.*?)```', re.DOTALL)
        # 查找所有匹配的内容\n
        matches = pattern.findall(text)
        return matches

    @staticmethod
    def extract_solution(solution_str, reward_fn):
        # TODO 抽取</think>tag之后的内容
        if not solution_str:
            return None

        # 查找</think>tag
        think_end = solution_str.find("</think>")
        if think_end != -1:
            solution_str = solution_str[think_end + len("</think>"):].strip()

        # 获取要提取的key
        index = reward_fn.find("codefuse/")
        if index != -1:
            reward_fn = reward_fn[index + len("codefuse/"):]

        matches = Post.extract_pattern(solution_str, "json")
        if matches:
            try:
                match = json.loads(matches[-1])
                return match[reward_fn]
            except Exception as e:
                return solution_str
        return solution_str

    @staticmethod
    def extract_path(content):
        """
        从文本中提取所有 'Path: <path>' 里的 <path>。
        返回路径列表，保留出现顺序。
        """
        #  (?m) 多行模式；^Path: 固定行首；\s* 吃掉空格；(.+?) 非贪婪到行尾
        return re.findall(r'(?m)^Path:\s*(.+?)\s*$', content)

    @staticmethod
    def extract_html(content, pattern):
        """
        抽取<{pattern}>xxx</{pattern}>中的xxx内容，支持换行。

        :param content: 要抽取的文本内容
        :param pattern: HTML标签名
        :return: 抽取的内容列表，保留出现顺序
        """
        # 使用非贪婪匹配，支持换行符
        regex = fr'<{pattern}>(.*?)</{pattern}>'
        matches = re.findall(regex, content, re.DOTALL)
        return [match.strip() for match in matches]


if __name__ == "__main__":
    content = '''<output>
```python:xxx/xxx.py
....
```

```python:xxx/xxx.py
....
```
</output>
'''
    path = Post.extract_html(content, pattern="output")
    print(path)
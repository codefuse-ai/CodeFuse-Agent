import subprocess

def run_cmd(cmd, repo_directory=None, verbose=True, return_stderr=False, timeout=None):
    try:
        process = subprocess.Popen(
            cmd,
            cwd=repo_directory,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True
        )

        import threading

        output_lines = []
        stderr_lines = []

        def read_output(pipe, lines, verbose_output=False):
            for line in iter(pipe.readline, ''):
                if line:
                    if verbose_output:
                        print(line, end='', flush=True)
                    lines.append(line)
            pipe.close()

        stdout_thread = threading.Thread(target=read_output, args=(process.stdout, output_lines, verbose))
        stderr_thread = threading.Thread(target=read_output,
                                         args=(process.stderr, stderr_lines, verbose and not return_stderr))

        for t in [stdout_thread, stderr_thread]:
            t.daemon = True
            t.start()

        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise subprocess.TimeoutExpired(cmd, timeout)

        for t in [stdout_thread, stderr_thread]:
            t.join()

        if process.returncode != 0:
            stderr_output = ''.join(stderr_lines)
            print(f"命令执行失败: {stderr_output}")
            raise subprocess.CalledProcessError(process.returncode, cmd, stderr=stderr_output)

        return "".join(output_lines)
    except subprocess.TimeoutExpired:
        print(f"命令执行超时: {timeout}秒")
        raise RuntimeError(f"命令执行超时: {timeout}秒")
    except subprocess.CalledProcessError as e:
        msg = "".join(output_lines)
        if return_stderr:
            return msg + "\n" + e.stderr if e.stderr else msg
        raise RuntimeError(msg)

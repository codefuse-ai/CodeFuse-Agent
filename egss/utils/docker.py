from utils.cmd_utils import run_cmd


class Docker:
    def __init__(self, image_name, container_name):
        # 镜像名称
        self.image_name = image_name
        # 运行时的docker名称
        self.container_name = container_name

        self.docker_id = None
        self.actual_image_name = None
        self.preprocess()

    def exist(self):
        # 查看当前的self.runtime_name是否存在正在运行的docker镜像
        cmd = f"docker ps --filter name={self.container_name} --format " + '{{.ID}}'
        docker_id = run_cmd(cmd)
        if docker_id:
            print(f"存在正在运行的docker: {docker_id}")
            return docker_id
        return None

    def find_actual_image_name(self):
        """根据image_name前缀查找实际的docker镜像名称"""
        try:
            # 获取所有本地镜像
            cmd = "docker images --format '{{.Repository}}:{{.Tag}}'"
            images = run_cmd(cmd, verbose=False)
            if not images:
                return self.image_name

            # 查找匹配的镜像
            for image in images.strip().split('\n'):
                image = image.strip()
                if image.startswith(self.image_name):
                    print(f"找到匹配的docker镜像: {image}")
                    return image

            # 如果没有找到匹配的，返回原始image_name
            return self.image_name
        except Exception:
            return self.image_name

    def preprocess(self):
        # 如果存在正在运行的self.runtime_name的镜像则立即关停
        if self.exist():
            print("找到正在运行的docker，关闭")
            self.shutdown()

    def run(self):
        try:
            print(f"启动当前docker")

            # 查找实际的镜像名称
            self.actual_image_name = self.find_actual_image_name()

            self.docker_id = run_cmd(
                f"docker run -d --name {self.container_name} {self.actual_image_name} tail -f /dev/null")
            self.docker_id = self.docker_id.strip()
            return True
        except Exception as e:
            return False

    def exec_cmd(self, cmd, verbose=False, return_stderr=False, timeout=None):
        cmd = self.get_docker_cmd(self.docker_id, cmd)
        print(f"执行 {cmd}")
        print("执行中...")
        return run_cmd(cmd, verbose=verbose, return_stderr=return_stderr, timeout=timeout)

    def cp(self, src, dst):
        return run_cmd(cmd=f"docker cp {src} {self.container_name}:{dst}", verbose=False)

    def shutdown(self):
        print(f"关闭当前docker...")
        run_cmd(f"docker stop {self.container_name}")
        run_cmd(f"docker rm -f {self.container_name}")
        self.docker_id = None

    @staticmethod
    def get_docker_cmd(docker_id, cmd):
        return f"docker exec -i {docker_id} bash -c '{cmd}'"
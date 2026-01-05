def install(docker, package_path):
    docker.cp(package_path, "/tmp/cfuse")
    docker.exec_cmd("pipx install /tmp/cfuse", verbose=False)
    docker.exec_cmd("mkdir -p /workspace/logs", verbose=False)
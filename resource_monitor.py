import psutil

# import GPUtil


# 200 MB
MINIMUM_VIRTUAL_MEMORY_REQUIRED = 200 * 1024 * 1024
# 1 Core
MINIMUM_CPU_CORES_REQUIRED = 1


def checkIfResourceAvailable():
    memory = psutil.virtual_memory()
    if memory.available < MINIMUM_VIRTUAL_MEMORY_REQUIRED:
        return False

    # elif psutil.cpu_count(logical=False) < MINIMUM_CPU_CORES_REQUIRED:
    #     return False

    # try:
    #     gpus = GPUtil.getGPUs()
    #     if not gpus or gpus[0].memoryFree < 500:
    #         return False
    # except ImportError:
    #     return False
    return True

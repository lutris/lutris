from lutris.util import drivers


nvidia = drivers.get_nvidia_driver_info()
print(nvidia)
gpu_id = drivers.get_nvidia_gpu_ids()[0]
print(drivers.get_gpu_info(gpu_id))

# pylint: disable=wildcard-import, unused-wildcard-import, invalid-name
# Vulkan detection by Patryk Obara (@dreamer)

"""Query Vulkan capabilities"""
# Standard Library
from ctypes import CDLL, POINTER, Structure, byref, c_char_p, c_int32, c_uint32, c_void_p, pointer, c_char, c_uint8, \
    c_uint64, c_float, c_size_t

VkResult = c_int32  # enum (size == 4)
VK_SUCCESS = 0
VK_ERROR_INITIALIZATION_FAILED = -3

VkStructureType = c_int32  # enum (size == 4)
VkBool32 = c_uint32
VK_STRUCTURE_TYPE_APPLICATION_INFO = 0
VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO = 1

VK_MAX_PHYSICAL_DEVICE_NAME_SIZE = 256
VK_UUID_SIZE = 16

VkInstanceCreateFlags = c_int32  # enum (size == 4)
VkPhysicalDeviceType = c_int32  # enum (size == 4)
VkSampleCountFlags = c_int32  # enum (size == 4)

VkInstance = c_void_p  # handle (struct ptr)
VkPhysicalDevice = c_void_p  # handle (struct ptr)
VkDeviceSize = c_uint64


def vk_make_version(major, minor, patch):
    """
    VK_MAKE_VERSION macro logic for Python

    https://www.khronos.org/registry/vulkan/specs/1.1-extensions/html/vkspec.html#fundamentals-versionnum
    """
    return c_uint32((major << 22) | (minor << 12) | patch)


def vk_api_version_major(version):
    return (version >> 22) & 0x7F


def vk_api_version_minor(version):
    return (version >> 12) & 0x3FF


def vk_api_version_patch(version):
    return version & 0xFFF


class VkApplicationInfo(Structure):
    """Python shim for struct VkApplicationInfo

    https://www.khronos.org/registry/vulkan/specs/1.1-extensions/man/html/VkApplicationInfo.html
    """

    # pylint: disable=too-few-public-methods

    _fields_ = [
        ("sType", VkStructureType),
        ("pNext", c_void_p),
        ("pApplicationName", c_char_p),
        ("applicationVersion", c_uint32),
        ("pEngineName", c_char_p),
        ("engineVersion", c_uint32),
        ("apiVersion", c_uint32),
    ]

    def __init__(self, name, version):
        super().__init__()
        self.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO
        self.pApplicationName = name.encode()
        self.applicationVersion = vk_make_version(*version)
        self.apiVersion = vk_make_version(1, 0, 0)


class VkInstanceCreateInfo(Structure):
    """Python shim for struct VkInstanceCreateInfo

    https://www.khronos.org/registry/vulkan/specs/1.1-extensions/man/html/VkInstanceCreateInfo.html
    """

    # pylint: disable=too-few-public-methods

    _fields_ = [
        ("sType", VkStructureType),
        ("pNext", c_void_p),
        ("flags", VkInstanceCreateFlags),
        ("pApplicationInfo", POINTER(VkApplicationInfo)),
        ("enabledLayerCount", c_uint32),
        ("ppEnabledLayerNames", c_char_p),
        ("enabledExtensionCount", c_uint32),
        ("ppEnabledExtensionNames", c_char_p),
    ]

    def __init__(self, app_info):
        super().__init__()
        self.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO
        self.pApplicationInfo = pointer(app_info)


class VkPhysicalDeviceLimits(Structure):
    _fields_ = [
        ("maxImageDimension1D", c_uint32),
        ("maxImageDimension2D", c_uint32),
        ("maxImageDimension3D", c_uint32),
        ("maxImageDimensionCube", c_uint32),
        ("maxImageArrayLayers", c_uint32),
        ("maxTexelBufferElements", c_uint32),
        ("maxUniformBufferRange", c_uint32),
        ("maxStorageBufferRange", c_uint32),
        ("maxPushConstantsSize", c_uint32),
        ("maxMemoryAllocationCount", c_uint32),
        ("maxSamplerAllocationCount", c_uint32),
        ("bufferImageGranularity", VkDeviceSize),
        ("sparseAddressSpaceSize", VkDeviceSize),
        ("maxBoundDescriptorSets", c_uint32),
        ("maxPerStageDescriptorSamplers", c_uint32),
        ("maxPerStageDescriptorUniformBuffers", c_uint32),
        ("maxPerStageDescriptorStorageBuffers", c_uint32),
        ("maxPerStageDescriptorSampledImages", c_uint32),
        ("maxPerStageDescriptorStorageImages", c_uint32),
        ("maxPerStageDescriptorInputAttachments", c_uint32),
        ("maxPerStageResources", c_uint32),
        ("maxDescriptorSetSamplers", c_uint32),
        ("maxDescriptorSetUniformBuffers", c_uint32),
        ("maxDescriptorSetUniformBuffersDynamic", c_uint32),
        ("maxDescriptorSetStorageBuffers", c_uint32),
        ("maxDescriptorSetStorageBuffersDynamic", c_uint32),
        ("maxDescriptorSetSampledImages", c_uint32),
        ("maxDescriptorSetStorageImages", c_uint32),
        ("maxDescriptorSetInputAttachments", c_uint32),
        ("maxVertexInputAttributes", c_uint32),
        ("maxVertexInputBindings", c_uint32),
        ("maxVertexInputAttributeOffset", c_uint32),
        ("maxVertexInputBindingStride", c_uint32),
        ("maxVertexOutputComponents", c_uint32),
        ("maxTessellationGenerationLevel", c_uint32),
        ("maxTessellationPatchSize", c_uint32),
        ("maxTessellationControlPerVertexInputComponents", c_uint32),
        ("maxTessellationControlPerVertexOutputComponents", c_uint32),
        ("maxTessellationControlPerPatchOutputComponents", c_uint32),
        ("maxTessellationControlTotalOutputComponents", c_uint32),
        ("maxTessellationEvaluationInputComponents", c_uint32),
        ("maxTessellationEvaluationOutputComponents", c_uint32),
        ("maxGeometryShaderInvocations", c_uint32),
        ("maxGeometryInputComponents", c_uint32),
        ("maxGeometryOutputComponents", c_uint32),
        ("maxGeometryOutputVertices", c_uint32),
        ("maxGeometryTotalOutputComponents", c_uint32),
        ("maxFragmentInputComponents", c_uint32),
        ("maxFragmentOutputAttachments", c_uint32),
        ("maxFragmentDualSrcAttachments", c_uint32),
        ("maxFragmentCombinedOutputResources", c_uint32),
        ("maxComputeSharedMemorySize", c_uint32),
        ("maxComputeWorkGroupCount", c_uint32 * 3),
        ("maxComputeWorkGroupInvocations", c_uint32),
        ("maxComputeWorkGroupSize", c_uint32 * 3),
        ("subPixelPrecisionBits", c_uint32),
        ("subTexelPrecisionBits", c_uint32),
        ("mipmapPrecisionBits", c_uint32),
        ("maxDrawIndexedIndexValue", c_uint32),
        ("maxDrawIndirectCount", c_uint32),
        ("maxSamplerLodBias", c_float),
        ("maxSamplerAnisotropy", c_float),
        ("maxViewports", c_uint32),
        ("maxViewportDimensions", c_uint32 * 2),
        ("viewportBoundsRange", c_float * 2),
        ("viewportSubPixelBits", c_uint32),
        ("minMemoryMapAlignment", c_size_t),
        ("minTexelBufferOffsetAlignment", VkDeviceSize),
        ("minUniformBufferOffsetAlignment", VkDeviceSize),
        ("minStorageBufferOffsetAlignment", VkDeviceSize),
        ("minTexelOffset", c_int32),
        ("maxTexelOffset", c_uint32),
        ("minTexelGatherOffset", c_int32),
        ("maxTexelGatherOffset", c_uint32),
        ("minInterpolationOffset", c_float),
        ("maxInterpolationOffset", c_float),
        ("subPixelInterpolationOffsetBits", c_uint32),
        ("maxFrameBufferWidth", c_uint32),
        ("maxFrameBufferHeight", c_uint32),
        ("maxFrameBufferLayers", c_uint32),
        ("frameBufferColorSampleCounts", VkSampleCountFlags),
        ("frameBufferDepthSampleCounts", VkSampleCountFlags),
        ("frameBufferStencilSampleCounts", VkSampleCountFlags),
        ("frameBufferNoAttachmentsSampleCounts", VkSampleCountFlags),
        ("maxColorAttachments", c_uint32),
        ("sampledImageColorSampleCounts", VkSampleCountFlags),
        ("sampledImageIntegerSampleCounts", VkSampleCountFlags),
        ("sampledImageDepthSampleCounts", VkSampleCountFlags),
        ("sampledImageStencilSampleCounts", VkSampleCountFlags),
        ("storageImageSampleCounts", VkSampleCountFlags),
        ("maxSampleMaskWords", c_uint32),
        ("timestampComputeAndGraphics", VkBool32),
        ("timestampPeriod", c_float),
        ("maxClipDistances", c_uint32),
        ("maxCullDistances", c_uint32),
        ("maxCombinedClipAndCullDistances", c_uint32),
        ("discreteQueuePriorities", c_uint32),
        ("pointSizeRange", c_float * 2),
        ("lineWidthRange", c_float * 2),
        ("pointSizeGranularity", c_float),
        ("lineWidthGranularity", c_float),
        ("strictLines", VkBool32),
        ("standardSampleLocations", VkBool32),
        ("optimalBufferCopyOffsetAlignment", VkDeviceSize),
        ("optimalBufferCopyRowPitchAlignment", VkDeviceSize),
        ("nonCoherentAtomSize", VkDeviceSize)
    ]


class VkPhysicalDeviceSparseProperties(Structure):
    _fields_ = [
        ("residencyStandard2DBlockShape", VkBool32),
        ("residencyStandard2DMultisampleBlockShape", VkBool32),
        ("residencyStandard3DBlockShape", VkBool32),
        ("residencyAlignedMipSize", VkBool32),
        ("residencyNonResidentStrict", VkBool32)
    ]


class VkPhysicalDeviceProperties(Structure):
    _fields_ = [
        ("apiVersion", c_uint32),
        ("driverVersion", c_uint32),
        ("vendorID", c_uint32),
        ("deviceID", c_uint32),
        ("deviceName", c_char * VK_MAX_PHYSICAL_DEVICE_NAME_SIZE),
        ("pipelineCacheUUID", c_uint8 * VK_UUID_SIZE),
        ("limits", VkPhysicalDeviceLimits),
        ("sparseProperties", VkPhysicalDeviceSparseProperties),
        ("space", c_uint32 * 512)
    ]


def is_vulkan_supported():
    """
    Returns True iff vulkan library can be loaded, initialized,
    and reports at least one physical device available.
    """
    try:
        vulkan = CDLL("libvulkan.so.1")
    except OSError:
        return False
    app_info = VkApplicationInfo("vkinfo", version=(0, 1, 0))
    create_info = VkInstanceCreateInfo(app_info)
    instance = VkInstance()
    result = vulkan.vkCreateInstance(byref(create_info), 0, byref(instance))
    if result != VK_SUCCESS:
        return False
    dev_count = c_uint32(0)
    result = vulkan.vkEnumeratePhysicalDevices(instance, byref(dev_count), 0)
    vulkan.vkDestroyInstance(instance, 0)
    return result == VK_SUCCESS and dev_count.value > 0


def get_vulkan_api_version_tuple():
    """
    Queries libvulkan to get the API version; if this library is missing
    it returns None. Returns a tuple of (major, minor, patch) version numbers.
    """
    try:
        vulkan = CDLL("libvulkan.so.1")
    except OSError:
        return None

    try:
        enumerate_instance_version = vulkan.vkEnumerateInstanceVersion
    except AttributeError:
        # Vulkan 1.0 did not have vkEnumerateInstanceVersion at all!
        return 1, 0

    version = c_uint32(0)
    result = enumerate_instance_version(byref(version))
    if result == VK_SUCCESS:
        major = vk_api_version_major(version.value)
        minor = vk_api_version_minor(version.value)
        patch = vk_api_version_patch(version.value)
        return major, minor, patch

    return None


def get_max_device_api_version_tuple():
    """
    Returns the greatest API version found among the physical devices
    """
    try:
        vulkan = CDLL("libvulkan.so.1")
    except OSError:
        return False
    app_info = VkApplicationInfo("vkinfo", version=(0, 1, 0))
    create_info = VkInstanceCreateInfo(app_info)
    instance = VkInstance()
    result = vulkan.vkCreateInstance(byref(create_info), 0, byref(instance))
    if result != VK_SUCCESS:
        return None
    dev_count = c_uint32(0)
    result = vulkan.vkEnumeratePhysicalDevices(instance, byref(dev_count), 0)
    if result != VK_SUCCESS or dev_count.value <= 0:
        return None

    devices = (VkPhysicalDevice * dev_count.value)()
    result = vulkan.vkEnumeratePhysicalDevices(instance, byref(dev_count), byref(devices))
    if result != VK_SUCCESS:
        return None

    versions = []
    getPhysicalDeviceProperties = vulkan.vkGetPhysicalDeviceProperties
    getPhysicalDeviceProperties.restype = None
    getPhysicalDeviceProperties.argtypes = [VkPhysicalDevice, c_void_p]  # pointer(VkPhysicalDeviceProperties)]

    for physical_device in devices:
        dev_props = VkPhysicalDeviceProperties()
        getPhysicalDeviceProperties(physical_device, byref(dev_props))

        major = vk_api_version_major(dev_props.apiVersion)
        minor = vk_api_version_minor(dev_props.apiVersion)
        patch = vk_api_version_patch(dev_props.apiVersion)
        versions.append((major, minor, patch))

    vulkan.vkDestroyInstance(instance, 0)
    return max(versions)

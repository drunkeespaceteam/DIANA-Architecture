cmake_minimum_required(VERSION 3.18)
project(synapse_infer CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ---------------------------------------------------------------------------
# LibTorch
#
# Download the CPU-only LibTorch archive from pytorch.org and unzip it, then
# point CMAKE_PREFIX_PATH at the extracted libtorch/ directory, e.g.:
#
#   cmake -DCMAKE_PREFIX_PATH=/path/to/libtorch ..
#
# Alternatively set the environment variable LIBTORCH_DIR and we pick it up:
# ---------------------------------------------------------------------------
if(DEFINED ENV{LIBTORCH_DIR})
    list(APPEND CMAKE_PREFIX_PATH $ENV{LIBTORCH_DIR})
endif()

find_package(Torch REQUIRED)

# ---------------------------------------------------------------------------
# Build target
# ---------------------------------------------------------------------------
add_executable(synapse_infer synapse_infer.cpp)

target_link_libraries(synapse_infer "${TORCH_LIBRARIES}")

# Torch headers require C++17.
set_property(TARGET synapse_infer PROPERTY CXX_STANDARD 17)

# On Windows, copy the required DLLs next to the executable.
if(MSVC)
    file(GLOB TORCH_DLLS "${TORCH_INSTALL_PREFIX}/lib/*.dll")
    add_custom_command(
        TARGET synapse_infer POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            ${TORCH_DLLS}
            $<TARGET_FILE_DIR:synapse_infer>
    )
endif()

# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------
install(TARGETS synapse_infer DESTINATION bin)

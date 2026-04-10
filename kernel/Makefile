# DIANA-Nexus Kernel Module Makefile
# Build against running kernel or custom WSL2 kernel
#
# Usage:
#   make                              # Build against running kernel
#   make KDIR=~/wsl2-kernel           # Build against custom WSL2 kernel
#   make KDIR=/path/to/kernel/source  # Build against any kernel source

obj-m += diana_core.o

# Multi-file kernel module
diana_core-objs := diana_core_main.o \
                   synapse_chip.o \
                   p2p_bus.o \
                   cpu_observer.o \
                   component_ram.o \
                   component_gpu.o \
                   component_ssd.o \
                   component_cache.o

# Extra compiler flags
ccflags-y := -DDIANA_VERSION=\"1.0\" -Wall -Werror

# Kernel directory — override with KDIR=... for custom kernels
KDIR ?= /lib/modules/$$(uname -r)/build

# Prepare source (handle naming collision)
prepare:
	@cp diana_core.c diana_core_main.c 2>/dev/null || true

# When called directly
all: prepare
	$(MAKE) -C $(KDIR) M=$$(pwd) modules

clean:
	$(MAKE) -C $(KDIR) M=$$(pwd) clean
	@rm -f diana_core_main.c

# NOTE: diana_core.c is compiled as diana_core_main.o
# to avoid name collision with the module object diana_core.o
# The 'prepare' target handles the copy automatically.

.PHONY: all clean module load unload test qemu iso usb status benchmark benchmark-quick setup-wsl

all: module userspace

module:
	@echo "Building DIANA kernel module..."
	@if [ -d /lib/modules/$$(uname -r)/build ]; then \
		cp kernel/diana_core.c kernel/diana_core_main.c; \
		$(MAKE) -C /lib/modules/$$(uname -r)/build M=$$(pwd)/kernel modules; \
		echo "Module built: kernel/diana_core.ko"; \
	else \
		echo "Kernel headers not found! Cannot build module."; \
	fi

userspace:
	@echo "Setting up userspace SYNAPSE..."
	pip3 install torch psutil --quiet || echo "Warning: pip deps failed"
	chmod +x scripts/*.sh tests/*.sh userspace/*.sh
	@echo "Userspace ready!"

load:
	@echo "Loading DIANA into kernel..."
	sudo insmod kernel/diana_core.ko || echo "Already loaded or error"
	@echo "Checking /proc/diana..."
	ls -l /proc/diana/ 2>/dev/null || echo "Not found"
	@echo "DIANA loaded! Check: cat /proc/diana/stats"

unload:
	@echo "Unloading DIANA from kernel..."
	sudo rmmod diana_core || echo "Not loaded or error"
	@echo "DIANA unloaded from kernel"

test:
	python3 tests/test_synapse.py
	bash tests/test_kernel_module.sh
	bash tests/test_p2p_bus.sh
	bash tests/test_integration.sh

qemu:
	bash scripts/run_qemu.sh

iso:
	bash scripts/make_iso.sh

usb:
	bash scripts/make_usb.sh

clean:
	@if [ -d /lib/modules/$$(uname -r)/build ]; then \
		$(MAKE) -C /lib/modules/$$(uname -r)/build M=$$(pwd)/kernel clean; \
	fi
	rm -f kernel/diana_core_main.c
	rm -f diana-os.iso diana-disk.img boot/bzImage boot/initramfs.cpio.gz
	rm -rf /var/lib/diana/models/* /tmp/diana_models/* 2>/dev/null || true
	@echo "Cleaned!"

status:
	@echo "=== DIANA Kernel Status ==="
	@cat /proc/diana/stats 2>/dev/null || echo "DIANA not loaded. Run: make load"
	@echo ""
	@cat /proc/diana/cpu_report 2>/dev/null || true
	@echo ""
	@echo "=== Recent P2P Bus Activity ==="
	@cat /proc/diana/p2p_log 2>/dev/null | tail -20 || true

benchmark:
	@echo "Running FULL benchmark comparison (Standard Linux vs DIANA)..."
	sudo bash scripts/run_benchmark.sh

benchmark-quick:
	@echo "Running QUICK benchmark comparison (~3 min)..."
	sudo bash scripts/run_benchmark.sh --quick

setup-wsl:
	@echo "Setting up WSL2 environment for DIANA-OS..."
	bash scripts/setup_wsl.sh

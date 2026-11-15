#!/usr/bin/env python3
"""Build BigSurface for the Surface Laptop 5 (Alder Lake-P) with the Command Line Tools only (no Xcode).

Changes against upstream BigSurface 8282631 (and its pinned submodules):
  * VoodooSerial: also match the ADL-P UART0 (8086:51a8) and run its 100 MHz LPSS clock
    at 64 MHz (M/N = 16/25), the clock the driver assumes for divisor 1 at 4 Mbaud.
  * VoodooGPIO: add the Tiger Lake-LP pin tables, which Linux also uses for ADL-P
    (ACPI INTC1055), taken from VoodooI2C/VoodooGPIO d415406.
Everything else is upstream source, built the way the Xcode projects build it.

Output: ~/Downloads/bigsurface-sl5/out/ with
  VoodooGPIO.kext VoodooSerial.kext VoodooInput.kext BigSurface.kext BigSurfaceHIDDriver.kext
Usage:  python3 ~/Downloads/build-bigsurface-sl5.py
"""
import os, plistlib, shutil, subprocess, sys
from pathlib import Path

CHECK = '--check' in sys.argv          # compile-only syntax check on a non-Mac machine
WORK = Path(os.environ.get('BSWORK', Path.home() / 'Downloads' / 'bigsurface-sl5'))
SRC, OUT, OBJ = WORK / 'src', WORK / 'out', WORK / 'obj'
PINS = {
    'BigSurface': ('https://github.com/Xiashangning/BigSurface.git', '82826312a429ede6e6f8441d49de2e2096b69ae4'),
    'VoodooGPIO-upstream': ('https://github.com/VoodooI2C/VoodooGPIO.git', 'd415406ecf25b5e322d3db9a4abab5719106fac1'),
}
LILU_TAG, VSMC_TAG = '1.7.2', '1.3.8'


def run(cmd, cwd=None):
    print('+', ' '.join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], cwd=cwd, check=True)


def checkout(url, sha, dest):
    # Fetch exactly the pinned commit (works even when it is not on the default branch).
    dest.mkdir(parents=True)
    run(['git', 'init', '-q'], cwd=dest)
    run(['git', 'fetch', '-q', '--depth', '1', url, sha], cwd=dest)
    run(['git', '-c', 'advice.detachedHead=false', 'checkout', '-q', 'FETCH_HEAD'], cwd=dest)


def fetch():
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    url, sha = PINS['BigSurface']
    checkout(url, sha, SRC)
    run(['git', 'remote', 'add', 'origin', url], cwd=SRC)
    run(['git', 'submodule', 'update', '--init', '-q'], cwd=SRC)
    url, sha = PINS['VoodooGPIO-upstream']
    checkout(url, sha, WORK / 'gpio-upstream')
    run(['git', 'clone', '-q', '--depth', '1', '--branch', LILU_TAG, 'https://github.com/acidanthera/Lilu.git', WORK / 'lilu'])
    run(['git', 'clone', '-q', '--depth', '1', '--branch', VSMC_TAG, 'https://github.com/acidanthera/VirtualSMC.git', WORK / 'vsmc'])


def replace_once(path, old, new):
    text = path.read_text()
    assert text.count(old) == 1, f'{path}: expected exactly one "{old[:60]}"'
    path.write_text(text.replace(old, new))


def patch():
    serial = SRC / 'Dependencies/VoodooSerial/VoodooSerial'
    replace_once(serial / 'Info.plist', '0x34a88086 0x9d278086', '0x34a88086 0x9d278086 0x51a88086')
    replace_once(serial / 'VoodooUART/VoodooUARTController.cpp',
                 '    else\n        LOG("Unknown UART type");',
                 '    else if (device.device_id == 0x51a8) // Alder Lake-P UART0: 100 MHz LPSS clock -> 64 MHz\n'
                 '        writeRegister(UART_UPDATE_CLK | CALC_CLK(16, 25) | UART_ENABLE_CLK, LPSS_PRIV + LPSS_UART_CLK);\n'
                 '    else\n        LOG("Unknown UART type");')

    gpio = SRC / 'Dependencies/VoodooGPIO/VoodooGPIO'
    up = WORK / 'gpio-upstream/VoodooGPIO/TigerLake-LP'
    dst = gpio / 'TigerLake-LP'
    dst.mkdir()
    hpp = (up / 'VoodooGPIOTigerLakeLP.hpp').read_text()
    cpp = (up / 'VoodooGPIOTigerLakeLP.cpp').read_text()
    for old, new in [('#include "../VoodooGPIOIntel.hpp"', '#include "../VoodooGPIO.hpp"'),
                     ('public VoodooGPIOIntel {', 'public VoodooGPIO {')]:
        assert hpp.count(old) == 1, old
        hpp = hpp.replace(old, new)
    for old, new in [('OSDefineMetaClassAndStructors(VoodooGPIOTigerLakeLP, VoodooGPIOIntel);',
                      'OSDefineMetaClassAndStructors(VoodooGPIOTigerLakeLP, VoodooGPIO);'),
                     ('return VoodooGPIOIntel::start(provider);', 'return VoodooGPIO::start(provider);')]:
        assert cpp.count(old) == 1, old
        cpp = cpp.replace(old, new)
    (dst / 'VoodooGPIOTigerLakeLP.hpp').write_text(hpp)
    (dst / 'VoodooGPIOTigerLakeLP.cpp').write_text(cpp)

    info = gpio / 'Info.plist'
    p = plistlib.loads(info.read_bytes())
    icl = p['IOKitPersonalities']['VoodooGPIOIceLakeLP']
    tgl = dict(icl)
    tgl['IOClass'] = 'VoodooGPIOTigerLakeLP'
    tgl['IONameMatch'] = ['INT34C5', 'INTC1055']
    p['IOKitPersonalities']['VoodooGPIOTigerLakeLP'] = tgl
    info.write_bytes(plistlib.dumps(p))


# name, bundle id, version, compat version override, source dir, extra include dirs
def kexts():
    d = SRC / 'Dependencies'
    return [
        ('VoodooGPIO', 'org.coolstar.VoodooGPIO', '1.2.0', d / 'VoodooGPIO/VoodooGPIO', []),
        ('VoodooSerial', 'com.xavier.VoodooSerial', '1.2', d / 'VoodooSerial/VoodooSerial', []),
        ('VoodooInput', 'me.kishorprins.VoodooInput', '1.1.3', d / 'VoodooInput/VoodooInput', []),
        ('BigSurface', 'com.xavier.BigSurface', '1.2.0', SRC / 'BigSurface/BigSurface',
         [WORK / 'lilu/Lilu', WORK / 'vsmc']),
        # its multitouch engine includes "../../Dependencies/VoodooInput/..." relative to the superproject
        ('BigSurfaceHIDDriver', 'com.xavier.BigSurfaceHIDDriver', '1.0.0', d / 'BigSurfaceHIDDriver/BigSurfaceHIDDriver',
         [SRC / 'BigSurface/BigSurface']),
    ]


TOOL = ['clang++', '-target', 'x86_64-apple-macosx10.12'] if CHECK else ['xcrun', 'clang++', '-arch', 'x86_64', '-mmacosx-version-min=10.12']
EXTRA = []


def probe_dtor_switch():
    # Newer clang turns global destructors (every OSMetaClass) into ___cxa_atexit calls,
    # which the kernel does not provide. Keep them in __mod_term_func like Xcode kexts.
    t = WORK / 'probe.cpp'
    t.write_text('struct A { ~A(); }; A a;\n')
    r = subprocess.run(TOOL + ['-mkernel', '-fapple-kext', '-mllvm', '-disable-atexit-based-global-dtor-lowering',
                               '-c', str(t), '-o', str(WORK / 'probe.o')], capture_output=True)
    if r.returncode == 0:
        EXTRA[:] = ['-mllvm', '-disable-atexit-based-global-dtor-lowering']
    print('== global dtor switch:', 'on' if EXTRA else 'not supported by this clang', flush=True)


def flags(name, version, includes):
    sdk = SRC / 'MacKernelSDK/Headers'
    tool = TOOL + EXTRA
    f = tool + ['-std=gnu++14', '-O2', '-g', '-mkernel', '-fapple-kext', '-fno-exceptions', '-fno-rtti',
                '-fno-builtin', '-fno-common', '-fno-stack-protector', '-fno-register-global-dtors-with-atexit', '-nostdinc', '-nostdinc++',
                '-DKERNEL', '-DKERNEL_PRIVATE', '-DDRIVER_PRIVATE', '-DAPPLE', '-DNeXT', '-D__APPLE__', '-D__MACH__',
                '-DPRODUCT_NAME=' + name, '-DMODULE_VERSION=' + version,
                '-I' + str(sdk), *['-I' + str(i) for i in includes],
                '-Wno-deprecated-declarations', '-Wno-c++11-narrowing', '-Wno-inconsistent-missing-override',
                '-Wno-unused-parameter', '-Wno-ossharedptr-misuse', '-Wno-unknown-warning-option',
                '-fdebug-compilation-dir=.', '-ffile-prefix-map=' + str(WORK) + '=/bigsurface-sl5']
    return f


KMOD_INFO = '''#include <mach/mach_types.h>
#ifndef __APPLE_CC__
#define __APPLE_CC__ 6000
#endif
extern kern_return_t _start(kmod_info_t *, void *);
extern kern_return_t _stop(kmod_info_t *, void *);
__attribute__((visibility("default"))) KMOD_EXPLICIT_DECL(%s, "%s", _start, _stop)
__private_extern__ kmod_start_func_t *_realmain = 0;
__private_extern__ kmod_stop_func_t *_antimain = 0;
__private_extern__ int _kext_apple_cc = __APPLE_CC__;
'''


def subst(obj, values):
    if isinstance(obj, dict):
        return {k: subst(v, values) for k, v in obj.items()}
    if isinstance(obj, list):
        return [subst(v, values) for v in obj]
    if isinstance(obj, str):
        for k, v in values.items():
            obj = obj.replace('$(%s)' % k, v)
        assert '$(' not in obj, 'unresolved build setting in Info.plist: ' + obj
    return obj


def build():
    OUT.mkdir(exist_ok=True)
    OBJ.mkdir(exist_ok=True)
    for name, ident, version, srcdir, includes in kexts():
        sources = sorted(srcdir.rglob('*.cpp'))
        objdir = OBJ / name
        objdir.mkdir(exist_ok=True)
        # Xcode's header map lets any project header be included by its bare name.
        hdirs = sorted({h.parent for h in srcdir.rglob('*') if h.suffix in ('.h', '.hpp')})
        cflags = flags(name, version, list(includes) + hdirs)
        objects = []
        for s in sources:
            o = objdir / (s.relative_to(srcdir).as_posix().replace('/', '_')[:-4] + '.o')
            run(cflags + ['-c', s, '-o', o])
            objects.append(o)
        info_c = objdir / (name + '_info.c')
        info_c.write_text(KMOD_INFO % (ident, version))
        cc = [x for x in cflags if x not in ('-std=gnu++14', '-nostdinc++', '-fno-rtti', '-fno-exceptions', '-fapple-kext')]
        cc[cc.index('clang++')] = 'clang'
        run(cc + ['-x', 'c', '-std=gnu11', '-c', info_c, '-o', objdir / (name + '_info.o')])
        objects.append(objdir / (name + '_info.o'))
        if CHECK:
            continue
        bundle = OUT / (name + '.kext') / 'Contents'
        if bundle.parent.exists():
            shutil.rmtree(bundle.parent)
        (bundle / 'MacOS').mkdir(parents=True)
        exe = bundle / 'MacOS' / name
        run(['xcrun', 'ld', '-arch', 'x86_64', '-kext', '-undefined', 'dynamic_lookup', '-no_fixup_chains',
             '-macos_version_min', '10.12', '-o', exe, *objects, SRC / 'MacKernelSDK/Library/x86_64/libkmod.a'])
        run(['xcrun', 'strip', '-S', exe])
        info = plistlib.loads((srcdir / 'Info.plist').read_bytes())
        info = subst(info, {'EXECUTABLE_NAME': name, 'PRODUCT_NAME': name, 'PRODUCT_BUNDLE_IDENTIFIER': ident,
                            'MARKETING_VERSION': version, 'CURRENT_PROJECT_VERSION': version, 'MODULE_VERSION': version,
                            'DEVELOPMENT_LANGUAGE': 'en', 'PRODUCT_BUNDLE_PACKAGE_TYPE': 'KEXT'})
        for k, v in [('CFBundleDevelopmentRegion', 'en'), ('CFBundleExecutable', name), ('CFBundleIdentifier', ident),
                     ('CFBundleInfoDictionaryVersion', '6.0'), ('CFBundleName', name), ('CFBundlePackageType', 'KEXT'),
                     ('CFBundleShortVersionString', version), ('CFBundleVersion', version)]:
            info.setdefault(k, v)
        (bundle / 'Info.plist').write_bytes(plistlib.dumps(info))
        syms = subprocess.check_output(['xcrun', 'nm', str(exe)], text=True)
        assert ' _kmod_info' in syms, name + ': missing kmod_info'
        undef = subprocess.check_output(['xcrun', 'nm', '-u', str(exe)], text=True).split()
        bad = [u for u in undef if u in ('___cxa_atexit', '___chkstk_darwin', '___memcpy_chk', '___memset_chk', '___stack_chk_fail_local')]
        assert not bad, name + ': imports symbols the kernel does not provide: ' + ' '.join(bad)
        print('== built %s %s (%d sources)' % (name, version, len(sources)), flush=True)


def main():
    if not CHECK:
        subprocess.run(['xcode-select', '-p'], check=True, stdout=subprocess.DEVNULL)
    if '--no-fetch' not in sys.argv:
        fetch()
        patch()
    probe_dtor_switch()
    build()
    if not CHECK:
        uart = (OUT / 'VoodooSerial.kext/Contents/Info.plist').read_bytes()
        assert b'0x51a88086' in uart
        gp = plistlib.loads((OUT / 'VoodooGPIO.kext/Contents/Info.plist').read_bytes())
        assert 'INTC1055' in gp['IOKitPersonalities']['VoodooGPIOTigerLakeLP']['IONameMatch']
        print('\nDone. Kexts are in', OUT)
        for k in sorted(OUT.glob('*.kext')):
            print('  ', k.name)


if __name__ == '__main__':
    main()

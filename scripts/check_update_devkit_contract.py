#!/usr/bin/env python3
"""Static counterpart to mocked Windows updater and real Docker boot tests."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def require(path,terms):
    text=(ROOT/path).read_text(encoding='utf-8-sig')
    for term in terms:
        if term not in text: raise SystemExit(path+': missing '+term)
    return text
def main():
    updater=require('update-devkit.ps1',('"--ff-only"','"--porcelain=v1"','Restart-UpdatedUpdater',
        'New-PreservedMountOverride','Get-MountSignature','Invoke-MigrationPlan','Assert-PostUpdate',
        '"build","--pull"','"up","-d","--force-recreate","--no-build"',
        '"stop","--time","30"','Initialize-GitPublishing','AUTOMATIC_REPAIR_USED=false'))
    if 'init-profiles.ps1' in updater or '-ArchiveLegacyProfiles' in updater: raise SystemExit('Legacy live initialization is still wired')
    if updater.count('"build","--pull"') != 1: raise SystemExit('Mutable latest must be built once')
    if not updater.index('"build","--pull"') < updater.index('"stop","--time","30"') < updater.index('"up","-d","--force-recreate","--no-build"'):
        raise SystemExit('Unsafe build/stop/recreate ordering')
    if updater.count('Invoke-MigrationPlan -Name $Container') != 3: raise SystemExit('Preflight required before build, before stop and after stop')
    require('init-lite.ps1', ('--read-only','--network','none',"':ro'",'--volumes-from', "'plan'", "'status'"))
    require('scripts/devkit-mounts.ps1', ('create_host_path = $false','external = $true','nocopy = $true','Get-MountSignature','ConvertTo-FlatMounts'))
    for bad in ('"down", "-v"','"volume", "rm"','"reset", "--hard"','"clean", "-fd"'):
        if bad in updater: raise SystemExit('Unsafe update operation: '+bad)
    print('[PASS] Fast-forward, read-only preflight, one build, exact mounts, mandatory boot migration')
if __name__=='__main__': main()

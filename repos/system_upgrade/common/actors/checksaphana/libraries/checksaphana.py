from leapp import reporting
from leapp.libraries.common.config import architecture, version
from leapp.libraries.stdlib import api
from leapp.models import SapHanaInfo

# SAP HANA Compatibility

SAP_HANA_MINIMAL_MAJOR_VERSION = 2

# RHEL 8.6 target requirements
SAP_HANA_RHEL86_REQUIRED_PATCH_LEVELS = ((5, 59, 2),)
SAP_HANA_RHEL86_MINIMAL_VERSION_STRING = 'HANA 2.0 SPS05 rev 59.02 or later'

# RHEL 9.0 target requirements
SAP_HANA_RHEL90_REQUIRED_PATCH_LEVELS = ((5, 59, 4), (6, 63, 0))
SAP_HANA_RHEL90_MINIMAL_VERSION_STRING = 'HANA 2.0 SPS05 rev 59.04 or later, or SPS06 rev 63 or later'


def _report_skip_check():
    if not api.current_actor().get_saphana_answer():
        summary = (
        'For the target RHEL releases >=8.8 and >=9.2 '
        'the leapp utility does not check RHEL and SAP HANA '
        'versions compatibility. Please ensure your SAP HANA '
        'is supported on the target RHEL release, '
        'otherwise proceed on your risk. '
        'SAP HANA: Supported Operating Systems '
        'https://launchpad.support.sap.com/#/notes/2235581')
    remedy_hint = ('BlaBla')

    reporting.create_report([
        reporting.Title('SAP HANA version should be checked'),
        reporting.Summary(summary),
        reporting.Severity(reporting.Severity.HIGH),
        reporting.Groups([reporting.Groups.SANITY]),
        reporting.Remediation(hint=remedy_hint),
        reporting.Groups([reporting.Groups.INHIBITOR]),
        reporting.Audience('sysadmin')
    ])
    
    summary = ('User has asserted the upgrade should proceed for '
               'the currently installed SAP HANA version.')
    reporting.create_report([
        reporting.Title('SAP HANA version has been checked'),
        reporting.Summary(summary),
        reporting.Severity(reporting.Severity.INFO),
        reporting.Groups([reporting.Groups.SANITY]),
        reporting.Audience('sysadmin')
    ])
    

def _manifest_get(manifest, key, default_value=None):
    for entry in manifest:
        if entry.key == key:
            return entry.value
    return default_value


def running_check(info):
    """ Creates a report if a running instance of SAP HANA has been detected """
    if info.running:
        reporting.create_report([
            reporting.Title('Found running SAP HANA instances'),
            reporting.Summary(
                'In order to perform a system upgrade it is necessary that all instances of SAP HANA are stopped.'
            ),
            reporting.RemediationHint('Shutdown all SAP HANA instances before you continue with the upgrade.'),
            reporting.Severity(reporting.Severity.HIGH),
            reporting.Groups([reporting.Groups.SANITY]),
            reporting.Groups([reporting.Groups.INHIBITOR]),
            reporting.Audience('sysadmin')
        ])


def _add_hana_details(target, instance):
    """ Adds instance information into the target dictionary for creating later reports. """
    target.setdefault(instance.name, {'numbers': set(), 'path': instance.path, 'admin': instance.admin})
    target[instance.name]['numbers'].add(instance.instance_number)


def _create_detected_instances_list(details):
    """ Generates report data for detected instances in list form with details """
    result = []
    for name, meta in details.items():
        result.append(('Name: {name}\n'
                       '  Instances: {instances}\n'
                       '  Admin: {admin}\n'
                       '  Path: {path}').format(name=name,
                                                instances=', '.join(meta['numbers']),
                                                admin=meta['admin'],
                                                path=meta['path']))
    if result:
        return '- {}'.format('\n- '.join(result))
    return ''


def _min_ver_string():
    if version.matches_target_version('8.6'):
        ver_str = SAP_HANA_RHEL86_MINIMAL_VERSION_STRING   
    else:
        ver_str = SAP_HANA_RHEL90_MINIMAL_VERSION_STRING
    return ver_str


def version1_check(info):
    """ Creates a report for SAP HANA instances running on version 1 """
    found = {}
    for instance in info.instances:
        if _manifest_get(instance.manifest, 'release') == '1.00':
            _add_hana_details(found, instance)

    if found:
        detected = _create_detected_instances_list(found)
        reporting.create_report([
            reporting.Title('Found SAP HANA 1 which is not supported with the target version of RHEL'),
            reporting.Summary(
                ('SAP HANA 1.00 is not supported with the version of RHEL you are upgrading to.\n\n'
                 'The following instances have been detected to be version 1.00:\n'
                 '{}'.format(detected))
            ),
            reporting.Severity(reporting.Severity.HIGH),
            reporting.RemediationHint(
                'In order to upgrade RHEL, you will have to upgrade your SAP HANA 1.00 software to'
                ' the version supported on the target RHEL release first.'),
            reporting.ExternalLink(url='https://launchpad.support.sap.com/#/notes/2235581',
                                   title='SAP HANA: Supported Operating Systems'),
            reporting.Groups([reporting.Groups.SANITY]),
            reporting.Groups([reporting.Groups.INHIBITOR]),
            reporting.Audience('sysadmin')
        ])


def _major_version_check(instance):
    """ Performs the check for the major version of SAP HANA """
    release = _manifest_get(instance.manifest, 'release', '0.00')
    parts = release.split('.')

    try:
        if int(parts[0]) != SAP_HANA_MINIMAL_MAJOR_VERSION:
            api.current_logger().info('Unsupported major version {} for instance {}'.format(release, instance.name))
            return False
        return True
    except (ValueError, IndexError):
        api.current_logger().warn(
            'Failed to parse manifest release field for instance {}'.format(instance.name), exc_info=True)
        return False


def _sp_rev_patchlevel_check(instance, patchlevels):
    """ Checks whether this SP, REV & PatchLevel are eligible """
    number = _manifest_get(instance.manifest, 'rev-number', '000')
    if len(number) > 2 and number.isdigit():
        required_sp_levels = [r[0] for r in patchlevels]
        lowest_sp = min(required_sp_levels)
        highest_sp = max(required_sp_levels)
        sp = int(number[0:2].lstrip('0') or '0')
        if sp < lowest_sp:
            # Less than minimal required SP
            return False
        if sp > highest_sp:
            # Less than minimal required SP
            return True
        for requirements in patchlevels:
            req_sp, req_rev, req_pl = requirements
            if sp == req_sp:
                rev = int(number.lstrip('0') or '0')
                if rev < req_rev:
                    continue
                if rev == req_rev:
                    patch_level = int(_manifest_get(instance.manifest, 'rev-patchlevel', '00').lstrip('0') or '0')
                    if patch_level < req_pl:
                        continue
                return True
        return False
    # if not 'len(number) > 2 and number.isdigit()'
    api.current_logger().warn(
        'Invalid rev-number field value `{}` in manifest for instance {}'.format(number, instance.name))
    return False


def _fullfills_hana_min_version(instance):
    """ Performs a check whether the version of SAP HANA fulfills the minimal requirements for the target RHEL """
    if version.matches_target_version('8.6'):
            patchlevels = SAP_HANA_RHEL86_REQUIRED_PATCH_LEVELS
    else:
        patchlevels = SAP_HANA_RHEL90_REQUIRED_PATCH_LEVELS
    return _major_version_check(instance) and _sp_rev_patchlevel_check(instance, patchlevels)


def version2_check(info):
    """ Performs all checks for SAP HANA 2 and creates a report if anything unsupported has been detected """
    found = {}
    for instance in info.instances:
        if _manifest_get(instance.manifest, 'release', None) == '1.00':
            continue
        if not _fullfills_hana_min_version(instance):
            _add_hana_details(found, instance)

    if found:
        min_ver_string = _min_ver_string()
        detected = _create_detected_instances_list(found)
        reporting.create_report([
            reporting.Title('SAP HANA needs to be updated before the RHEL upgrade'),
            reporting.Summary(
                ('A newer version of SAP HANA is required in order continue with the upgrade.'
                 ' {min_hana_version} is required for the target version of RHEL.\n\n'
                 'The following SAP HANA instances have been detected to be installed with a lower version'
                 ' than required on the target system:\n'
                 '{detected}').format(detected=detected, min_hana_version=min_ver_string)
            ),
            reporting.RemediationHint('Update SAP HANA at least to {}'.format(min_ver_string)),
            reporting.ExternalLink(url='https://launchpad.support.sap.com/#/notes/2235581',
                                   title='SAP HANA: Supported Operating Systems'),
            reporting.Severity(reporting.Severity.HIGH),
            reporting.Groups([reporting.Groups.SANITY]),
            reporting.Groups([reporting.Groups.INHIBITOR]),
            reporting.Audience('sysadmin')
        ])


def platform_check():
    """ Creates an inhibitor report in case the system is not running on x86_64 """
    if not architecture.matches_architecture(architecture.ARCH_X86_64):
        if version.get_target_major_version() == '8':
            elink = reporting.ExternalLink(
                url='https://access.redhat.com/solutions/5533441',
                title='How do I upgrade from Red Hat Enterprise Linux 7 to Red Hat Enterprise Linux 8 with SAP HANA')
        else:
            elink = reporting.ExternalLink(
                url='https://access.redhat.com/solutions/6980855',
                title='How to in-place upgrade SAP environments from RHEL 8 to RHEL 9')

        reporting.create_report([
            reporting.Title('SAP HANA upgrades are only supported on X86_64 systems'),
            reporting.Summary(
                ('Upgrades for SAP HANA are only supported on X86_64 systems.'
                 ' For more information please consult the documentation.')
            ),
            reporting.Severity(reporting.Severity.HIGH),
            reporting.Groups([reporting.Groups.SANITY]),
            reporting.Groups([reporting.Groups.INHIBITOR]),
            reporting.Audience('sysadmin'),
            elink,
        ])
        return False

    return True


def perform_check():
    """ Performs all checks for SAP HANA and will skip if the upgrade flavour is not `saphana` """

    if api.current_actor().configuration.flavour != 'saphana':
        # Do not run on non saphana upgrades
        return

    if not platform_check():
        # If this architecture is not supported, there's no sense in continuing.
        return

    info = next(api.consume(SapHanaInfo), None)
    if not info:
        return

    running_check(info)
    version1_check(info)
    version2_check(info)

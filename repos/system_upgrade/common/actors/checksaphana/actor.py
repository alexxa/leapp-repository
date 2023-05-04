from leapp.actors import Actor
from leapp.libraries.actor.checksaphana import perform_check
from leapp.libraries.common.config import version
from leapp.models import SapHanaInfo, SapHanaDesicion
from leapp.reporting import Report
from leapp.tags import ChecksPhaseTag, IPUWorkflowTag


class CheckSapHana(Actor):
    """
    If SAP HANA has been detected, several checks are performed to ensure a successful upgrade.

    If the upgrade flavour is 'default' no checks are being executed.

    The following checks are executed:
    - If the major target release is 8, and this system is _NOT_ running on x86_64, the upgrade is inhibited.
    - If the major target release is 9, and this system is _NOT running on x86_64 or ppc64le, 
      the upgrade is inhibited.
    - If SAP HANA 1 has been detected on the system the upgrade is inhibited since it is not supported
      for any target version.
    - If SAP HANA 2 has been detected, the upgrade will be inhibited if an unsupported version for the target release
      has been detected (<8.8 and <9.2).
    - CHECKSAPHANA defaults to producing inhibitory reports if a user doesn't agree to proceed
      for the currently installed SAP HANA 2 version and selected target RHEL version.  
    - If SAP HANA is running the upgrade is inhibited.
    """

    name = 'check_sap_hana'
    consumes = (SapHanaInfo,)
    produces = (Report,)
    tags = (IPUWorkflowTag, ChecksPhaseTag)
    dialogs = (
        Dialog(
            scope='confirm_upgrade_for_saphana_version',
            reason='Confirmation',
            components=(
                BooleanComponent(
                    key='confirm',
                    label='Do you want the upgrade proceed for '
                          'the currently installed SAP HANA 2.0 version?',
                    description='Enter True, otherwise the upgrade process '
                                'will be interrupted.',
                    reason='For the target RHEL releases >=8.8 and >=9.2 '
                           'the leapp utility does not check RHEL and SAP HANA '
                           'versions compatibility. Please ensure your SAP HANA '
                           'is supported on the target RHEL release, '
                           'otherwise proceed on your own risk. '
                           'SAP HANA: Supported Operating Systems '
                           'https://launchpad.support.sap.com/#/notes/2235581'
                ),
            )
        )
    )
    _asked_answer = False
    _saphana_answer = None
    
    def get_saphana_answer(self):
        if not self._asked_answer:
            self._asked_answer = True
            self._saphana_answer = self.get_answers(self.dialogs[0]).get('confirm')
        return self._saphana_answer

    def process(self):
        perform_check()

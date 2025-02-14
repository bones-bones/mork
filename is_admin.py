from discord import Member

import hc_constants


def is_admin(member: Member):
    return member.get_role(hc_constants.ADMIN) != None


def is_veto(member: Member):
    return member.get_role(hc_constants.VETO_COUNCIL) != None or member.get_role(
        hc_constants.VETO_COUNCIL_2
    )

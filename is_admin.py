from discord import Member

import hc_constants


def is_admin(member: Member):
    return member.get_role(hc_constants.ADMIN) != None
import json
import unittest
from unittest.mock import patch

from manage_arcgis_user_groups_helper_functions import is_user_org_in_allowed_orgs, get_user_group, proper_group_names


class TestManageArcgisUserGroupsHelperFunctions(unittest.TestCase):
    @patch("manage_arcgis_user_groups_helper_functions.redis_client.get", return_value=json.dumps(["USDA", "DOI"]))
    @patch("manage_arcgis_user_groups_helper_functions.get_user_group", return_value="['USDA']")
    def test_user_org_in_allowed_orgs(self, mock_redis_get, _):
        """Ensure user belongs to an allowed organization"""
        user_email = "user@usda.gov"
        result = is_user_org_in_allowed_orgs(user_email)
        self.assertTrue(result)

    @patch("manage_arcgis_user_groups_helper_functions.redis_client.get", return_value=None)
    @patch("manage_arcgis_user_groups_helper_functions.get_user_group", return_value="['USDA']")
    def test_user_org_not_in_allowed_orgs(self, mock_redis_get, _):
        """Ensure user does not belong to an allowed organization"""
        user_email = "user@unknown.gov"
        result = is_user_org_in_allowed_orgs(user_email)
        self.assertFalse(result)

    @patch("manage_arcgis_user_groups_helper_functions.redis_client.get", return_value=None)
    @patch("manage_arcgis_user_groups_helper_functions.get_user_group", return_value="['USDA']")
    def test_user_org_not_in_allowed_orgs_invalid_email(self, mock_redis_get, _):
        """Ensure invalid email returns False"""
        user_email = "user@invalid"
        result = is_user_org_in_allowed_orgs(user_email)
        self.assertFalse(result)

    @patch("manage_arcgis_user_groups_helper_functions.redis_client.get", return_value=None)
    @patch("manage_arcgis_user_groups_helper_functions.get_user_group", return_value="['USDA']")
    def test_user_is_user_org_allowed_non_usda(self, mock_redis_get, _):
        """Ensure invalid email returns False"""
        user_email = "user@epa.gov"
        result = is_user_org_in_allowed_orgs(user_email)
        self.assertTrue(result)

    @patch("manage_arcgis_user_groups_helper_functions.redis_client.get", return_value=None)
    @patch("manage_arcgis_user_groups_helper_functions.get_user_group", return_value="['USDA']")
    def test_epa_in_EPA(self, _, a):
        user_group = get_user_group("user@epa.gov")
        org = proper_group_names.get(user_group)
        self.assertEqual(org, "EPA")

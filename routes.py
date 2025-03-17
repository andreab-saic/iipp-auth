from urllib import parse

from flask import Blueprint, request, jsonify, redirect, session, make_response, render_template_string
import json
import logging
import requests
import time
import redis
from threading import Thread

from config import (redis_client, ARCGIS_CLIENT_URL, ARCGIS_OIDC_CLIENT_ID, ARCGIS_LOGIN_REDIRECT_URL, \
                    ARCGIS_LOGIN_CALLBACK_URL, USER_NOT_IN_ALLOWED_AGENCY_REDIRECT_DELAY_SECONDS, PUBLIC_URL,
                    AUTH_SERVICE_DOMAIN,
                    USER_NOT_IN_ALLOWED_AGENCY_URL, SELF_SELECT_GROUP_FORM_URL)

from token_generation import (
    generate_auth_code,
    generate_jwt_token,
    generate_nonce,
    generate_oidc_state,
    get_auth_code_from_idp,
    construct_idp_userinfo_get,
    construct_idp_token_post,
    handle_idp_token_response, handle_userinfo_response, parse_x509_subject, parse_auth_access
)
from manage_arcgis_user_groups_helper_functions import (
    get_arcgis_group_titles,
    is_user_group_in_arcgis,
    assign_user_to_groups,
    is_user_org_in_allowed_orgs, is_user_selected_group_in_arcgis_groups, parent_groups
)
from redis_helpers import (
    get_username_to_email,
    get_email_to_user_groups,
    put_username_to_email,
    delete_username_to_email,
    delete_user_auth_access,
    delete_email_to_user_groups,
    get_access_token_to_userinfo,
    get_auth_code_to_access_token, get_user_auth_access, put_user_auth_access, create_user,
    put_auth_code_to_access_token, put_access_token_to_userinfo
)
from arcgis_api import (
    get_user_from_username
)

# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler('./routes.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

routes_blueprint = Blueprint("routes", __name__)

# -------------------------
# ✅ ArcGIS Callback Route
# -------------------------
@routes_blueprint.route('/arcgis_callback')
def arcgis_callback():
    try:
        logger.info("Starting arcgis_callback route")
        arcgis_auth_code = generate_auth_code()
        arcgis_access_token = generate_jwt_token(ARCGIS_CLIENT_URL, ARCGIS_OIDC_CLIENT_ID)

        put_auth_code_to_access_token(arcgis_auth_code, arcgis_access_token)

        userinfo = request.cookies.get('userinfo') or redis_client.get(f"userinfo:{arcgis_access_token}")
        if userinfo:
            userinfo = json.loads(userinfo)
        else:
            return "Error: UID missing in user info", 400

        put_access_token_to_userinfo(arcgis_access_token, json.dumps(userinfo))

        response = make_response(redirect(f'{ARCGIS_LOGIN_REDIRECT_URL}?code={arcgis_auth_code}'))
        response.set_cookie("userinfo", json.dumps(userinfo), httponly=True, secure=True, max_age=3600)

        return response
    except Exception as e:
        logger.error(f"Error in arcgis_callback: {str(e)}")
        return "Internal server error", 500

# -------------------------
# ✅ User Not in Allowed Groups UI
# -------------------------
@routes_blueprint.route('/user_not_in_allowed_groups')
def user_not_in_allowed_groups():
    try:
        redirect_delay_seconds = redis_client.get('redirect_delay_seconds') or USER_NOT_IN_ALLOWED_AGENCY_REDIRECT_DELAY_SECONDS
        public_site_url = redis_client.get('public_site_url') or PUBLIC_URL

        redis_client.setex('redirect_delay_seconds', 86400, redirect_delay_seconds)
        redis_client.setex('public_site_url', 86400, public_site_url)
    except redis.RedisError as e:
        return "An error occurred while fetching data from Redis.", 500

    return render_template_string("""
    <html>
      <head>
        <meta http-equiv="refresh" content="{{ redirect_delay_seconds }};url={{ public_site_url }}">
        <style>
          body {
            background-color: #f0f0f0;
            color: #4c4c4c;
            font-family: "Avenir Next W01","Avenir Next W00","Avenir Next","Avenir","Helvetica Neue",sans-serif;
            font-style: normal;
            letter-spacing: 0em;
            font-kerning: normal;
            text-rendering: optimizeLegibility;
            font-feature-settings: "liga" 1, "calt" 0;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
          }
          .centered-box, .arcgis-login-header {
            width: 400px;
            text-align: center;
            border-radius: 2px;
          }
          .centered-box {
            background-color: #fff;
            box-shadow: 2px 2px 1px -1px rgba(0,0,0,0.15);
            padding: 10px;
          }
          .arcgis-login-header {
            padding: 10px 0px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 1.25rem;
            background-color: #f0f0f0;
          }
          .arcgis-login-header p {
            margin: 0;
            text-align: left;
          }
          .arcgis-login-header svg {
            margin-left: auto;
          }
        </style>
      </head>
      <body>
        <div class="arcgis-login-header">
          <p>Sign in to ArcGIS Enterprise</p>
          <svg id="gnav-dist-esri-Australia-tm" xmlns="http://www.w3.org/2000/svg" width="84" height="30" viewBox="0 0 84 30" focusable="false"><title>Esri</title>
            <g><path d="M77.377.695a2.51615,2.51615,0,0,0-2.5536,2.4884,2.58969,2.58969,0,0,0,5.1756,0A2.512,2.512,0,0,0,77.377.695ZM75.4635,24.12065h3.892V8.5485h-3.892ZM40.615,8.1597c-4.7019,0-8.4646,3.2749-8.4646,8.1744,0,4.89828,3.7627,8.17661,8.4646,8.17661a8.08656,8.08656,0,0,0,5.8516-2.31047L44.0102,19.7439a4.96654,4.96654,0,0,1-3.781,1.65148,4.03745,4.03745,0,0,1-4.1869-3.69818H47.9167V16.6269C47.9167,11.2076,44.9662,8.1597,40.615,8.1597Zm-4.5727,6.6168a3.87339,3.87339,0,0,1,4.023-3.6991c2.4334,0,3.9261,1.4292,3.9603,3.6991Zm17.3044-1.8482c0-1.1689,1.2333-1.655,2.2729-1.655a3.53132,3.53132,0,0,1,3.0376,1.5764l2.476-2.4735a6.83011,6.83011,0,0,0-5.418-2.2165c-3.1469,0-6.2621,1.5555-6.2621,5.0284,0,5.9379,8.4026,3.4059,8.4026,6.6172,0,1.23253-1.4594,1.78384-2.5946,1.78384a4.75239,4.75239,0,0,1-3.6905-1.905l-2.5144,2.5136a7.64753,7.64753,0,0,0,5.9779,2.313c3.1784,0,6.717-1.29823,6.717-4.99731C61.7511,13.4459,53.3467,15.7175,53.3467,12.9283Zm14.151-1.9166h-.0623V8.5485H63.5426V24.12065h3.8928V15.7815a3.91438,3.91438,0,0,1,4.1848-3.9252,7.452,7.452,0,0,1,1.7181.253l.1519-3.7259a5.03109,5.03109,0,0,0-1.3826-.2237A4.96277,4.96277,0,0,0,67.4977,11.0117ZM14.782,2.9606a10.41336,10.41336,0,0,0-2.651.2599.49091.49091,0,0,0-.6431.4729.65358.65358,0,0,0,.2394.5615,20.045,20.045,0,0,1,2.4735,2.1423c-.4694.0517-.9807.1379-1.5039.2462-.5847-1.264-2.4653-.1147-3.71354-.0648-.14639.006-.28684.0252-.43149.035A20.32772,20.32772,0,0,1,8.3415,3.6934a17.20722,17.20722,0,0,1,6.875-1.6255l.3721-.0098c.3124-.0027.3371-.2514.0435-.2915A13.53793,13.53793,0,0,0,8.35348,2.9124,14.41291,14.41291,0,0,0,.89854,10.791c-.44337,1.2475-2.21826,7.1947.935,12.29948a13.20182,13.20182,0,0,0,9.88737,6.6769,14.15347,14.15347,0,0,0,8.7522-1.05577c5.9511-2.64154,10.4956-12.55841,5.9499-19.747C24.6289,5.6461,19.9278,2.7361,14.782,2.9606ZM12.5233,7.6083a17.75423,17.75423,0,0,1,2.3616-.3686,15.74087,15.74087,0,0,1,1.7479,2.5404c-.8053.3896-1.8781.6879-2.3146,1.3123a1.78056,1.78056,0,0,0-.2318.9943,23.589,23.589,0,0,0-3.8774,1.2862c-.45286-1.3319-.85009-2.659-1.12365-3.8421C10.3814,8.2941,11.8985,8.0927,12.5233,7.6083Zm6.6103,15.87993c-.3546.03749-.7071.08277-1.0169.13057a14.62456,14.62456,0,0,0-2.6843.72209,43.94209,43.94209,0,0,1-2.6676-4.43649A15.48586,15.48586,0,0,1,18.54,18.4602a4.61747,4.61747,0,0,0,.6909.9559C19.9871,20.1902,18.7892,21.299,19.1336,23.48823ZM10.5303,14.3485a19.29324,19.29324,0,0,1,3.5604-1.2862,2.03511,2.03511,0,0,1-.1827.903,2.50151,2.50151,0,0,0,.1336,1.7748c.7549,1.0985,2.0083.4882,2.9518.8834a2.15739,2.15739,0,0,1,.9633.8389,16.049,16.049,0,0,0-5.7053,1.4109A41.82526,41.82526,0,0,1,10.5303,14.3485Zm.8321,4.9371c-.0699.0333-.145.0742-.2171.1101-1.1019-.3073-1.78517-.478-3.25617-.7801a3.08944,3.08944,0,0,0-2.15123.1758c-.15959.0461-.3128.0879-.46173.1323-.14893-.3815-.29663-.7768-.44556-1.2018a27.12084,27.12084,0,0,1,4.82187-2.9851C10.1514,16.2283,10.8665,18.2204,11.3624,19.2856Zm.7674,4.52863a9.48665,9.48665,0,0,0,.6047-1.88965c.5692.95763,1.2487,1.9989,1.7744,2.814A17.3346,17.3346,0,0,0,11.837,26.4243,11.23781,11.23781,0,0,1,12.1298,23.81423ZM17.4642,9.1779c-.0102.0145-.0282.0261-.0393.0401a23.04534,23.04534,0,0,0-1.3771-2.1111,21.90906,21.90906,0,0,1,3.3743.1084C18.4082,7.5781,17.9609,8.4687,17.4642,9.1779Zm-9.028,1.0938c.01836-.0256.03837-.0465.05716-.0717.23344,1.1821.51294,2.1606.88552,3.5178a33.49783,33.49783,0,0,0-4.976,2.9723,17.18753,17.18753,0,0,1-.5889-1.9465,1.77168,1.77168,0,0,1,1.47617-1.325C6.51758,13.2957,7.57083,11.4696,8.43624,10.2717ZM3.0267,8.4883A15.96075,15.96075,0,0,1,7.74876,3.9686a26.225,26.225,0,0,0,.21806,2.6928q-.85463.0852-1.69211.2109a12.08231,12.08231,0,0,0-3.11438,4.0878A14.926,14.926,0,0,1,3.0267,8.4883ZM2.16984,9.9256s.06188,1.0601.1131,1.8329a11.90283,11.90283,0,0,0-1.17919,1.5914A9.53467,9.53467,0,0,1,2.16984,9.9256Zm7.664,18.35671A12.62638,12.62638,0,0,1,1.72131,20.029a17.47511,17.47511,0,0,1-.65164-6.473.65293.65293,0,0,0,.38018.0167c.13486-.0922.61581-.4302.95763-.7277.00472.0393.01241.0892.01792.1314a12.04271,12.04271,0,0,0-.40064,2.7099,19.25881,19.25881,0,0,1,1.28616,1.7062c-.31061.2304-.9051.6418-1.04468.7417a.62859.62859,0,0,0-.114,1.0148.56565.56565,0,0,0,.6124-.0103,10.69141,10.69141,0,0,1,1.06609-.769c.151.3926.29182.7468.43052,1.0848a1.34447,1.34447,0,0,0-.34269.79893,2.46079,2.46079,0,0,0,1.91875,2.35994c.035.01022.06057.01363.09388.02307.0499.07508.09517.14674.14761.22357A5.74221,5.74221,0,0,0,5.03032,23.9226c-.13189.17244-.28125.43018-.15959.48139a2.1227,2.1227,0,0,0,.71824-.03408c.46644-.08967.82618-.606,1.14833-.7955a17.99721,17.99721,0,0,0,1.67159,1.87942c.02866.11947.05506.24576.08792.3516a7.47254,7.47254,0,0,0,.495,1.19578A12.16213,12.16213,0,0,0,10.456,27.562,8.34474,8.34474,0,0,0,9.83383,28.28231Zm.98917.31236a4.36881,4.36881,0,0,1,.5054-.6256c.4672.30983.9682.66493,1.3677.89366A9.59947,9.59947,0,0,1,10.823,28.59467Zm3.1128.30983a22.07987,22.07987,0,0,1-2.0088-1.47057,14.04631,14.04631,0,0,1,3.1281-1.88878c.4016.63076,1.7267,2.50678,2.2575,3.11184A17.30216,17.30216,0,0,1,13.9358,28.9045Zm6.7055-1.50806a16.58869,16.58869,0,0,1-2.2045.98742,23.42994,23.42994,0,0,1-2.4402-3.20141,13.9527,13.9527,0,0,1,3.3466-.82111,7.49493,7.49493,0,0,0,.4438,1.09423,2.51925,2.51925,0,0,0,.6486.85345c.0853-.05287.1644-.11519.2484-.16981C20.678,26.55828,20.6665,26.98505,20.6413,27.39644ZM20.3106,5.9188c-.2702-.1719-.6068-.1079-.4669.1933a4.06966,4.06966,0,0,0,.4272.5122,19.53821,19.53821,0,0,0-4.856-.3645,15.62334,15.62334,0,0,0-2.8614-2.7649c4.999-.3111,9.4897,1.7565,11.4737,4.1856a15.42616,15.42616,0,0,0-2.6677-.9628A5.95374,5.95374,0,0,0,20.3106,5.9188Zm1.0946,21.06538c.023-.40711.0402-.92267.0529-1.39637a12.11693,12.11693,0,0,0,1.3695-1.23757,12.42379,12.42379,0,0,1,1.4275.23895A11.02525,11.02525,0,0,1,21.4052,26.98418Zm3.8245-3.72467a4.1318,4.1318,0,0,1-.6328.89444,9.77165,9.77165,0,0,0-1.2722-.37468c.0786-.09387.1635-.18267.2395-.27915.2688-1.7957-.3376-2.371.4211-4.01392.053-.1144.111-.2407.1716-.3713a11.3497,11.3497,0,0,1,1.1526.3858A30.26049,30.26049,0,0,1,25.2297,23.25951Zm-.7079-4.91621c.1959-.4072.4118-.8399.6456-1.2708.0607.5479.1042,1.0813.1307,1.5635C25.0578,18.5302,24.7936,18.4346,24.5218,18.3433Zm2.2178,1.1257-.1937.75629a18.08656,18.08656,0,0,1-.8318,2.22245,25.61647,25.61647,0,0,0,.1481-2.72944.59489.59489,0,0,0,.5586-.3414c.0568-.1946-.5637-.495-.5637-.495a20.74328,20.74328,0,0,0-.1725-2.7001c.1426-.2292.2869-.452.4341-.6551a12.095,12.095,0,0,0-.1852-1.5743,1.21486,1.21486,0,0,0,.323.0747c.2825.0043.2817-.1899.1912-.2978a3.78494,3.78494,0,0,0-.6423-.4195,12.02044,12.02044,0,0,0-2.7811-5.3203,14.9875,14.9875,0,0,1,1.7548.7732,9.39245,9.39245,0,0,1,2.2114,4.9204A12.16755,12.16755,0,0,1,26.7396,19.469Z"></path><path d="M80.9857,8.7917V8.5528h1.2188v.2389H81.736V9.9832h-.2835V8.7917Zm1.87-.2389L83.221,9.577l.3679-1.0242h.4062V9.9832h-.262V8.8293l-.396,1.1539h-.2287l-.3995-1.1539V9.9832h-.262V8.5528Z"></path></g>
          </svg>
        </div>
        <div class="centered-box">
          <p>Sorry… your account could not be created due to one of the following:</p>
          <p>The Login.gov account you're attempting to sign in with is using a personal/non-agency email, in which case you'll need to set your federal email as the primary email in your Login.gov account. (Tutorial available, linked at bottom of homepage.)</p>
          <p>Or your agency is not currently partnered with the IIPP, in which case we encourage you to contact your agency's imagery hosting administrator to inquire about partnering into the IIPP.</p>

          <p>Redirecting you to IIPP public site in {{ redirect_delay_seconds }} seconds...</p>
          <p><a href="{{ public_site_url }}">Click here to redirect now</a></p>
        </div>
      </body>
    </html>
    """, public_site_url=PUBLIC_URL, redirect_delay_seconds=USER_NOT_IN_ALLOWED_AGENCY_REDIRECT_DELAY_SECONDS)

# -------------------------
# ✅ Group Selection UI
# -------------------------
@routes_blueprint.route('/select_user_groups', methods=['GET', 'POST'])
def select_user_groups():
    if request.method == 'GET':
        user_email = request.args.get('email', '')
        user_first_name = request.args.get('first_name', '')
        user_last_name = request.args.get('last_name', '')
        select_group_options = ""

        for usda_subgroup in parent_groups['usda']:
            select_group_options += f'<option value="{usda_subgroup}">{usda_subgroup.upper()}</option>'

        redis_client.setex("usda_group_options", 86400, select_group_options)

        return render_template_string("""
    <html>
      <head>
        <style>
          body {
            background-color: #f0f0f0;
            color: #4c4c4c;
            font-family: "Avenir Next W01","Avenir Next W00","Avenir Next","Avenir","Helvetica Neue",sans-serif;
            font-style: normal;
            letter-spacing: 0em;
            font-kerning: normal;
            text-rendering: optimizeLegibility;
            font-feature-settings: "liga" 1, "calt" 0;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
          }
          .centered-box, .arcgis-login-header {
            width: 400px;
            text-align: center;
            border-radius: 2px;
          }
          .centered-box {
            background-color: #fff;
            box-shadow: 2px 2px 1px -1px rgba(0,0,0,0.15);
            padding: 10px;
          }
          .arcgis-login-header {
            padding: 10px 0px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 1.25rem;
            background-color: #f0f0f0;
          }
          .arcgis-login-header p {
            margin: 0;
            text-align: left;
          }
          .arcgis-login-header svg {
            margin-left: auto;
          }
        </style>
      </head>
      <body>
        <div class="arcgis-login-header">
          <p>Sign in to ArcGIS Enterprise</p>
          <svg id="gnav-dist-esri-Australia-tm" xmlns="http://www.w3.org/2000/svg" width="84" height="30" viewBox="0 0 84 30" focusable="false"><title>Esri</title>
            <g><path d="M77.377.695a2.51615,2.51615,0,0,0-2.5536,2.4884,2.58969,2.58969,0,0,0,5.1756,0A2.512,2.512,0,0,0,77.377.695ZM75.4635,24.12065h3.892V8.5485h-3.892ZM40.615,8.1597c-4.7019,0-8.4646,3.2749-8.4646,8.1744,0,4.89828,3.7627,8.17661,8.4646,8.17661a8.08656,8.08656,0,0,0,5.8516-2.31047L44.0102,19.7439a4.96654,4.96654,0,0,1-3.781,1.65148,4.03745,4.03745,0,0,1-4.1869-3.69818H47.9167V16.6269C47.9167,11.2076,44.9662,8.1597,40.615,8.1597Zm-4.5727,6.6168a3.87339,3.87339,0,0,1,4.023-3.6991c2.4334,0,3.9261,1.4292,3.9603,3.6991Zm17.3044-1.8482c0-1.1689,1.2333-1.655,2.2729-1.655a3.53132,3.53132,0,0,1,3.0376,1.5764l2.476-2.4735a6.83011,6.83011,0,0,0-5.418-2.2165c-3.1469,0-6.2621,1.5555-6.2621,5.0284,0,5.9379,8.4026,3.4059,8.4026,6.6172,0,1.23253-1.4594,1.78384-2.5946,1.78384a4.75239,4.75239,0,0,1-3.6905-1.905l-2.5144,2.5136a7.64753,7.64753,0,0,0,5.9779,2.313c3.1784,0,6.717-1.29823,6.717-4.99731C61.7511,13.4459,53.3467,15.7175,53.3467,12.9283Zm14.151-1.9166h-.0623V8.5485H63.5426V24.12065h3.8928V15.7815a3.91438,3.91438,0,0,1,4.1848-3.9252,7.452,7.452,0,0,1,1.7181.253l.1519-3.7259a5.03109,5.03109,0,0,0-1.3826-.2237A4.96277,4.96277,0,0,0,67.4977,11.0117ZM14.782,2.9606a10.41336,10.41336,0,0,0-2.651.2599.49091.49091,0,0,0-.6431.4729.65358.65358,0,0,0,.2394.5615,20.045,20.045,0,0,1,2.4735,2.1423c-.4694.0517-.9807.1379-1.5039.2462-.5847-1.264-2.4653-.1147-3.71354-.0648-.14639.006-.28684.0252-.43149.035A20.32772,20.32772,0,0,1,8.3415,3.6934a17.20722,17.20722,0,0,1,6.875-1.6255l.3721-.0098c.3124-.0027.3371-.2514.0435-.2915A13.53793,13.53793,0,0,0,8.35348,2.9124,14.41291,14.41291,0,0,0,.89854,10.791c-.44337,1.2475-2.21826,7.1947.935,12.29948a13.20182,13.20182,0,0,0,9.88737,6.6769,14.15347,14.15347,0,0,0,8.7522-1.05577c5.9511-2.64154,10.4956-12.55841,5.9499-19.747C24.6289,5.6461,19.9278,2.7361,14.782,2.9606ZM12.5233,7.6083a17.75423,17.75423,0,0,1,2.3616-.3686,15.74087,15.74087,0,0,1,1.7479,2.5404c-.8053.3896-1.8781.6879-2.3146,1.3123a1.78056,1.78056,0,0,0-.2318.9943,23.589,23.589,0,0,0-3.8774,1.2862c-.45286-1.3319-.85009-2.659-1.12365-3.8421C10.3814,8.2941,11.8985,8.0927,12.5233,7.6083Zm6.6103,15.87993c-.3546.03749-.7071.08277-1.0169.13057a14.62456,14.62456,0,0,0-2.6843.72209,43.94209,43.94209,0,0,1-2.6676-4.43649A15.48586,15.48586,0,0,1,18.54,18.4602a4.61747,4.61747,0,0,0,.6909.9559C19.9871,20.1902,18.7892,21.299,19.1336,23.48823ZM10.5303,14.3485a19.29324,19.29324,0,0,1,3.5604-1.2862,2.03511,2.03511,0,0,1-.1827.903,2.50151,2.50151,0,0,0,.1336,1.7748c.7549,1.0985,2.0083.4882,2.9518.8834a2.15739,2.15739,0,0,1,.9633.8389,16.049,16.049,0,0,0-5.7053,1.4109A41.82526,41.82526,0,0,1,10.5303,14.3485Zm.8321,4.9371c-.0699.0333-.145.0742-.2171.1101-1.1019-.3073-1.78517-.478-3.25617-.7801a3.08944,3.08944,0,0,0-2.15123.1758c-.15959.0461-.3128.0879-.46173.1323-.14893-.3815-.29663-.7768-.44556-1.2018a27.12084,27.12084,0,0,1,4.82187-2.9851C10.1514,16.2283,10.8665,18.2204,11.3624,19.2856Zm.7674,4.52863a9.48665,9.48665,0,0,0,.6047-1.88965c.5692.95763,1.2487,1.9989,1.7744,2.814A17.3346,17.3346,0,0,0,11.837,26.4243,11.23781,11.23781,0,0,1,12.1298,23.81423ZM17.4642,9.1779c-.0102.0145-.0282.0261-.0393.0401a23.04534,23.04534,0,0,0-1.3771-2.1111,21.90906,21.90906,0,0,1,3.3743.1084C18.4082,7.5781,17.9609,8.4687,17.4642,9.1779Zm-9.028,1.0938c.01836-.0256.03837-.0465.05716-.0717.23344,1.1821.51294,2.1606.88552,3.5178a33.49783,33.49783,0,0,0-4.976,2.9723,17.18753,17.18753,0,0,1-.5889-1.9465,1.77168,1.77168,0,0,1,1.47617-1.325C6.51758,13.2957,7.57083,11.4696,8.43624,10.2717ZM3.0267,8.4883A15.96075,15.96075,0,0,1,7.74876,3.9686a26.225,26.225,0,0,0,.21806,2.6928q-.85463.0852-1.69211.2109a12.08231,12.08231,0,0,0-3.11438,4.0878A14.926,14.926,0,0,1,3.0267,8.4883ZM2.16984,9.9256s.06188,1.0601.1131,1.8329a11.90283,11.90283,0,0,0-1.17919,1.5914A9.53467,9.53467,0,0,1,2.16984,9.9256Zm7.664,18.35671A12.62638,12.62638,0,0,1,1.72131,20.029a17.47511,17.47511,0,0,1-.65164-6.473.65293.65293,0,0,0,.38018.0167c.13486-.0922.61581-.4302.95763-.7277.00472.0393.01241.0892.01792.1314a12.04271,12.04271,0,0,0-.40064,2.7099,19.25881,19.25881,0,0,1,1.28616,1.7062c-.31061.2304-.9051.6418-1.04468.7417a.62859.62859,0,0,0-.114,1.0148.56565.56565,0,0,0,.6124-.0103,10.69141,10.69141,0,0,1,1.06609-.769c.151.3926.29182.7468.43052,1.0848a1.34447,1.34447,0,0,0-.34269.79893,2.46079,2.46079,0,0,0,1.91875,2.35994c.035.01022.06057.01363.09388.02307.0499.07508.09517.14674.14761.22357A5.74221,5.74221,0,0,0,5.03032,23.9226c-.13189.17244-.28125.43018-.15959.48139a2.1227,2.1227,0,0,0,.71824-.03408c.46644-.08967.82618-.606,1.14833-.7955a17.99721,17.99721,0,0,0,1.67159,1.87942c.02866.11947.05506.24576.08792.3516a7.47254,7.47254,0,0,0,.495,1.19578A12.16213,12.16213,0,0,0,10.456,27.562,8.34474,8.34474,0,0,0,9.83383,28.28231Zm.98917.31236a4.36881,4.36881,0,0,1,.5054-.6256c.4672.30983.9682.66493,1.3677.89366A9.59947,9.59947,0,0,1,10.823,28.59467Zm3.1128.30983a22.07987,22.07987,0,0,1-2.0088-1.47057,14.04631,14.04631,0,0,1,3.1281-1.88878c.4016.63076,1.7267,2.50678,2.2575,3.11184A17.30216,17.30216,0,0,1,13.9358,28.9045Zm6.7055-1.50806a16.58869,16.58869,0,0,1-2.2045.98742,23.42994,23.42994,0,0,1-2.4402-3.20141,13.9527,13.9527,0,0,1,3.3466-.82111,7.49493,7.49493,0,0,0,.4438,1.09423,2.51925,2.51925,0,0,0,.6486.85345c.0853-.05287.1644-.11519.2484-.16981C20.678,26.55828,20.6665,26.98505,20.6413,27.39644ZM20.3106,5.9188c-.2702-.1719-.6068-.1079-.4669.1933a4.06966,4.06966,0,0,0,.4272.5122,19.53821,19.53821,0,0,0-4.856-.3645,15.62334,15.62334,0,0,0-2.8614-2.7649c4.999-.3111,9.4897,1.7565,11.4737,4.1856a15.42616,15.42616,0,0,0-2.6677-.9628A5.95374,5.95374,0,0,0,20.3106,5.9188Zm1.0946,21.06538c.023-.40711.0402-.92267.0529-1.39637a12.11693,12.11693,0,0,0,1.3695-1.23757,12.42379,12.42379,0,0,1,1.4275.23895A11.02525,11.02525,0,0,1,21.4052,26.98418Zm3.8245-3.72467a4.1318,4.1318,0,0,1-.6328.89444,9.77165,9.77165,0,0,0-1.2722-.37468c.0786-.09387.1635-.18267.2395-.27915.2688-1.7957-.3376-2.371.4211-4.01392.053-.1144.111-.2407.1716-.3713a11.3497,11.3497,0,0,1,1.1526.3858A30.26049,30.26049,0,0,1,25.2297,23.25951Zm-.7079-4.91621c.1959-.4072.4118-.8399.6456-1.2708.0607.5479.1042,1.0813.1307,1.5635C25.0578,18.5302,24.7936,18.4346,24.5218,18.3433Zm2.2178,1.1257-.1937.75629a18.08656,18.08656,0,0,1-.8318,2.22245,25.61647,25.61647,0,0,0,.1481-2.72944.59489.59489,0,0,0,.5586-.3414c.0568-.1946-.5637-.495-.5637-.495a20.74328,20.74328,0,0,0-.1725-2.7001c.1426-.2292.2869-.452.4341-.6551a12.095,12.095,0,0,0-.1852-1.5743,1.21486,1.21486,0,0,0,.323.0747c.2825.0043.2817-.1899.1912-.2978a3.78494,3.78494,0,0,0-.6423-.4195,12.02044,12.02044,0,0,0-2.7811-5.3203,14.9875,14.9875,0,0,1,1.7548.7732,9.39245,9.39245,0,0,1,2.2114,4.9204A12.16755,12.16755,0,0,1,26.7396,19.469Z"></path><path d="M80.9857,8.7917V8.5528h1.2188v.2389H81.736V9.9832h-.2835V8.7917Zm1.87-.2389L83.221,9.577l.3679-1.0242h.4062V9.9832h-.262V8.8293l-.396,1.1539h-.2287l-.3995-1.1539V9.9832h-.262V8.5528Z"></path></g>
          </svg>
        </div>
        <div class="centered-box">
          <h4>Additional ArcGIS Login Step for Users with a USDA.gov Email Address</h4>
          <h5>Please identify the government organization you are most closely associated with from the dropdown.</h5>
          <form action=""" + f'"{SELF_SELECT_GROUP_FORM_URL}"' + """ method="post">
              <input type="hidden" name="email" value="{{ email }}">
              <input type="hidden" name="firstname" value="{{ user_first_name }}">
              <input type="hidden" name="lastname" value="{{ user_last_name }}">
              <select name="group" required>
                <option value="" disabled selected>Select a group</option>
                {{ select_group_options|safe }}
              </select>
              <br>
              <br>
              <input type="submit" value="Submit">
          </form>
        </div>
      </body>
    </html>
    """, email=user_email, user_first_name=user_first_name, user_last_name=user_last_name, select_group_options=select_group_options)

    elif request.method == 'POST':
        selected_group = request.form.get('group')
        user_email = request.form.get('email')
        logger.debug(f'Setting group select for for {user_email} to group {selected_group}')

        if not selected_group or not user_email:
            return "Invalid submission", 400

        redis_client.setex(f"user:{user_email}:selected_group", 3600, selected_group)
        return redirect(ARCGIS_LOGIN_CALLBACK_URL)

# -------------------------
# ✅ Auth Route
# -------------------------
@routes_blueprint.route('/auth')
def auth():
    response = make_response(get_auth_code_from_idp())

    # Clear old session coookies
    response.set_cookie("session", "", expires=0)

    # Set a new session cookie
    response.set_cookie("session", "new_session_value", httponly=True, secure=True, samesite="Lax")
    
    return response

# -------------------------
# ✅ Add Users to Groups Route
# -------------------------
@routes_blueprint.route('/add_user_to_groups', methods=['POST'])
def add_user_to_groups_route():
    """
    Route to add users to groups based on the event data.
    Handles user creation, update, and deletion events.
    """
    data = request.get_json()
    event = data['events'][0]
    operation = event['operation']
    source = event['source']

    user_was_created = operation == 'add' and source == 'users'
    user_was_updated = operation == 'update' and source == 'users'
    user_was_deleted = operation == 'delete' and source == 'user'

    # Handle user creation or update
    if user_was_created or user_was_updated:
        username = event['username']
        user = get_user_from_username(username)
        user_email = user.get('email')

        # Store username-to-email mapping in Redis
        put_username_to_email(username, user_email)

        # Handle group assignment for created user
        if user_was_created:
            user_groups = get_email_to_user_groups(user_email)
            if user_groups:
                # Assign user to their self-selected groups from Redis
                selected_groups = json.loads(user_groups['user_groups'])
                for group_title in selected_groups:
                    # Check if the group exists in Redis
                    if is_user_group_in_arcgis(group_title):
                        # Group exists, assign the user to the group
                        assign_user_to_groups(username, group_title)
                    else:
                        logger.info(f"Group '{group_title}' not found in ArcGIS groups.")
            else:
                # If no groups selected, assign user to default groups from Redis
                default_groups = get_arcgis_group_titles()
                for group_title in default_groups:
                    # Assign the user to each default group
                    assign_user_to_groups(username, group_title)

    # Handle user deletion
    elif user_was_deleted:
        username = event['id']
        user_email_dict = get_username_to_email(username)
        user_email = user_email_dict['user_email']

        # Delete user-related data from Redis and other systems
        delete_username_to_email(username)
        delete_user_auth_access(user_email)
        delete_email_to_user_groups(user_email)

    return 'OK', 200

# -------------------------
# ✅ User Info Route
# -------------------------
@routes_blueprint.route('/userinfo')
def userinfo_route():
    auth_header = request.headers.get('Authorization')
    arcgis_access_token = auth_header[7:]
    try:
        userinfo = get_access_token_to_userinfo(arcgis_access_token)['userinfo']
        if not userinfo:
            return jsonify({"error": "Token invalid or expired"}), 401
        return jsonify(json.loads(userinfo))
    except KeyError:
        return 'Unauthorized', 401


# -------------------------
# ✅ Token Route
# -------------------------
@routes_blueprint.route('/token', methods=['POST'])
def token():
    arcgis_auth_code = request.form.get('code')
    arcgis_access_token = get_auth_code_to_access_token(arcgis_auth_code)['access_token']

    return jsonify({
        "access_token": arcgis_access_token,
        "token_type": "Bearer",
        "expires_in": 3600,
    })

# -------------------------
# ✅ ArcGIS Webhook Route
# -------------------------
@routes_blueprint.route('/arcgis_webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if data.get('events') is None:
        return 'OK', 200
    Thread(target=lambda: requests.post(f'https://{AUTH_SERVICE_DOMAIN}/add_user_to_groups', json=data)).start()
    return 'OK', 200

# -------------------------
# ✅ Special Bypass Users & Groups
# -------------------------
SPECIAL_USDA_USERS = {
    "andrea_borghi@ios.doi.gov",
    "john_gillham@ios.doi.gov",
    "satish_bobburi@ios.doi.gov"
}

SPECIAL_USDA_DOMAINS = {
    # "specialagency.gov",
    # "examplemilitary.mil",
    "@usda.gov"
}

def is_usda_user(user_email):
    """Check if the user is in the special bypass list or domain."""
    if user_email in SPECIAL_USDA_USERS:
        return True
    for domain in SPECIAL_USDA_DOMAINS:
        if user_email.endswith(domain):
            return True
    return False

# -------------------------
# ✅ Authentication Functions
# -------------------------
@routes_blueprint.route('/generate_auth_code', methods=['POST'])
def generate_auth_code_endpoint():
    auth_code, access_token = generate_auth_code()
    return jsonify({"auth_code": auth_code, "access_token": access_token})


# -------------------------
# ✅ Callback
# -------------------------

@routes_blueprint.route('/callback', methods=['GET'])
def callback():
    """Handle IDP callback and authenticate user."""
    auth_code = request.args.get('code')
    if not auth_code:
        return 'Authorization code missing', 400

    token_url, headers, data = construct_idp_token_post(auth_code)
    logger.debug(f'Requesting token with URL: {token_url}')
    idp_token_response = requests.post(token_url, headers=headers, data=data)

    access_token = handle_idp_token_response(idp_token_response)
    logger.debug(f'Access token received: {access_token}')

    userinfo_url, headers = construct_idp_userinfo_get(access_token)
    logger.debug(f'Requesting user info from {userinfo_url}')

    userinfo_response = requests.get(userinfo_url, headers=headers)
    userinfo = handle_userinfo_response(userinfo_response)

    if not userinfo:
        return "Error: Userinfo missing", 400

    x509_subject = userinfo.get('x509_subject')
    user_email = userinfo.get('email')

    if x509_subject:
        given_name, family_name, organizations = parse_x509_subject(x509_subject)
        userinfo['organizations'] = organizations
    else:
        logger.info(f'No x509 subject found, using email to set names for {user_email}')
        # given_name = user_email.split('@')[0]
        # family_name = user_email.split('@')[1].split('.')[-2]
        given_name = userinfo.get('given_name', user_email.split('@')[0])
        family_name = userinfo.get('family_name', user_email.split('@')[1].split('.')[-2])

    userinfo['given_name'] = given_name
    userinfo['family_name'] = family_name

    # is this referenced later?
    redis_client.set(f"{user_email}:userinfo:{access_token}", json.dumps(userinfo))

    logger.info(f'User info processed for email: {user_email}')
    # I don't see how this is never None since the put doesn't happen unless this is None?
    user_permission_data = get_user_auth_access(user_email)

    # ✅ Apply Bypass Check
    # this isn't really the bypass as its inside really just inside of is_usda_user
    if is_usda_user(user_email):
        logger.info(f"Bypass activated for {user_email} - forcing USDA access.")
        user_is_usda = True
        user_is_in_allowed_orgs = True
    else:
        user_is_usda = False
        user_is_in_allowed_orgs = is_user_org_in_allowed_orgs(user_email)

    user_has_selected_group = False

    # this is if users have logged in before and have data in redis
    if user_permission_data is not None:
        (user_is_disallowed,
         user_has_selected_group,
         user_previous_selected_group) = parse_auth_access(user_permission_data.get('auth_access'))

        if user_is_disallowed is True:

            logger.warning(f'User {user_email} is disallowed. Checking for USDA and selected group.')
            if user_is_usda is True and user_previous_selected_group is not None:
                is_previous_selected_group_in_arcgis_groups = is_user_selected_group_in_arcgis_groups(
                    user_previous_selected_group)

                if is_previous_selected_group_in_arcgis_groups:
                    logger.info(f'User {user_email} is allowed to re-select group {user_previous_selected_group}')
                    user_is_disallowed = False
                    user_has_selected_group = False
                    # user_previous_selected_group = None
                    user_permission_data = {
                        'is_disallowed': user_is_disallowed,
                        'has_selected_group': user_has_selected_group,
                    }

                    put_user_auth_access(user_email, user_permission_data)

                    # Update Redis cache with updated `has_selected_group`

                    redis_client.set(f"{user_email}:has_selected_group", user_has_selected_group)

                else:
                    logger.warning(
                        f'User {user_email} not allowed to select group {user_previous_selected_group}. Redirecting.')
                    return redirect(USER_NOT_IN_ALLOWED_AGENCY_URL)

        if user_is_disallowed is False:
            resp = redirect(ARCGIS_LOGIN_CALLBACK_URL)
            resp.set_cookie('userinfo', json.dumps(userinfo))

            if user_is_usda is False:
                logger.debug(f'User {user_email} is not USDA, redirecting to {ARCGIS_LOGIN_CALLBACK_URL}')
                return resp

            if user_is_usda is True and user_has_selected_group is True:
                logger.info(f'User {user_email} is USDA and has selected a group, redirecting.')
                return resp

    # if the user has never logged in, is not usda and is not in allowed orgs
    if not user_is_in_allowed_orgs:
        logger.warning(
            f'User {user_email} is not in allowed organizations, redirecting to {USER_NOT_IN_ALLOWED_AGENCY_URL}')

        return redirect(USER_NOT_IN_ALLOWED_AGENCY_URL)


    logger.info(f'User first name: {given_name}, last name: {family_name}')

    # this section is for entirely new users that have no data in redis
    # or for users that have logged in before but have not selected a group
    if user_is_usda and user_has_selected_group is False:
        logger.info(f'User {user_email} is USDA and has not selected a group, redirecting to self-select form.')

        self_select_form_url = parse.urljoin(SELF_SELECT_GROUP_FORM_URL,
                                                    f"?email={user_email}&firstname={given_name}&lastname={family_name}")

        resp = redirect(self_select_form_url)
        resp.set_cookie('userinfo', json.dumps(userinfo))
        return resp


    logger.debug(f'Creating user data for {user_email} and redirecting to {ARCGIS_LOGIN_CALLBACK_URL}')
    user_permission_data = {
        'is_disallowed': False,
        'has_selected_group': False
    }

    create_user(user_email, user_permission_data)
    resp = redirect(ARCGIS_LOGIN_CALLBACK_URL)
    resp.set_cookie('userinfo', json.dumps(userinfo))
    return resp

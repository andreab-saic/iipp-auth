from types import SimpleNamespace

AUTH = SimpleNamespace(
    IDP=SimpleNamespace(
        BASE_URL='https://idp.int.identitysandbox.gov',
        AUTHORIZATION_ROUTE='/openid_connect/authorize',
        TOKEN_ROUTE='/api/openid_connect/token',
        USERINFO_ROUTE='/api/openid_connect/userinfo',
        ACR_VALUE='http://idmanagement.gov/ns/assurance/ial/1',
        CLIENT_ID='urn:gov:gsa:openidconnect.profiles:sp:sso:doi:iipp-arcgis-auth-stg',
        PROMPT='select_account',
        REDIRECT_URI='https://iipp-arcgis-auth-stg.geoplatform.gov/callback',
        RESPONSE_TYPE='code',
        SCOPE='openid+email+x509+x509_subject',
        CLIENT_ASSERTION_TYPE='urn:ietf:params:oauth:client-assertion-type:jwt-bearer'
    )
)
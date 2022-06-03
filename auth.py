import requests
from params import app_id, secret, reddit_username, reddit_password

auth = requests.auth.HTTPBasicAuth(app_id, secret)

data = {
    'grant_type': 'password',
    'username': reddit_username,
    'password': reddit_password
}
headers = {'User-Agent': 'automation/0.0.1'}
res = requests.post('https://www.reddit.com/api/v1/access_token', auth=auth, data=data, headers=headers)

token = res.json()['access_token']
headers['Authorization'] = 'bearer {}'.format(token)
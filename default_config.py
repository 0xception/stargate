"""
Configuration file for starGate.py.
"""

## AMI Configuration
ami = {
    'host': 'voip.example.net',
    'port': 5038,
    'username': 'asterisk',
    'password': 'password'
}

## FastAGI Configuration
agi = {
    'port': 24131
}

## Database Configuration
db = {
    'type': 'MySQLdb',
    'host': '127.0.0.1',
    'username': 'user',
    'password': 'password',
    'database': 'stargate'
}

plugins = {}

plugins['records'] = {}

## Callback Plugin Configration
plugins['queue'] = {
    'port': 24131,
    'interval': 90,
    'queues': ['Dev'],
    'callback_limit': 3,
    'callback': {
        'trunk': '13193656200',
        'exten': 's',
        'priority': 1,
        'context': 'queue-callback',
        'callerid': '18663552318',
        'timeout':30000
    }
}


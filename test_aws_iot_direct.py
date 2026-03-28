from awscrt import io, mqtt
from awsiot import mqtt_connection_builder

ENDPOINT = "ajfzkitfnbpep-ats.iot.us-east-1.amazonaws.com"
CLIENT_ID = "direct-test-home1"
CERT_PATH = "C:/FogAndEdge/certs/681bfabc3534e8c803c61dd80a4e59a30da009fde618eb8fa39b627a4959f6cd-certificate.pem.crt"
KEY_PATH = "C:/FogAndEdge/certs/681bfabc3534e8c803c61dd80a4e59a30da009fde618eb8fa39b627a4959f6cd-private.pem.key"
CA_PATH = "C:/FogAndEdge/certs/AmazonRootCA1.pem"

event_loop_group = io.EventLoopGroup(1)
host_resolver = io.DefaultHostResolver(event_loop_group)
client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

connection = mqtt_connection_builder.mtls_from_path(
    endpoint=ENDPOINT,
    cert_filepath=CERT_PATH,
    pri_key_filepath=KEY_PATH,
    client_bootstrap=client_bootstrap,
    ca_filepath=CA_PATH,
    client_id=CLIENT_ID,
    clean_session=True,
    keep_alive_secs=30
)

print("Connecting...")
connection.connect().result()
print("Connected successfully")
connection.disconnect().result()
print("Disconnected")
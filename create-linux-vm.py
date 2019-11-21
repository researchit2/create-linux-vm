import os
import time
import uuid
import json
import secrets

from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.compute.models import ResourceIdentityType
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.keyvault import KeyVaultManagementClient
from azure.keyvault import KeyVaultAuthentication, KeyVaultClient, KeyVaultId
from azure.mgmt.resource.resources.models import DeploymentMode
from msrestazure.azure_exceptions import CloudError


azure_tenant_id = os.environ.get("AZURE_TENANT_ID")
azure_object_id = os.environ.get("AZURE_OBJECT_ID")
azure_client_id = os.environ.get("AZURE_CLIENT_ID")
azure_secret_id = os.environ.get("AZURE_SECRET_ID")
subscription_id = os.environ.get("AZURE_SUBSCR_ID")
cost_center_tag = os.environ.get("COST_CENTER_TAG")
service_tag = os.environ.get("SERVICE_TAG")
created_by = os.environ.get("CREATED_BY_TAG")


def main():
    resource_group_name = os.environ.get("RESOURCE_GROUP_NAME")
    resource_location = os.environ.get("RESOURCE_LOCATION")
    unique_number = create_unique_number()
    unique_id = str(create_uuid())

    if azure_tenant_id is None:
        exit(print("Missing AZURE_TENANT_ID"))

    if azure_object_id is None:
        exit(print("Missing AZURE_OBJECT_ID"))

    if azure_client_id is None:
        exit(print("Missing AZURE_CLIENT_ID"))

    if azure_secret_id is None:
        exit(print("Missing AZURE_SECRET_ID"))

    if subscription_id is None:
        exit(print("Missing AZURE_SUBSCR_ID"))

    if cost_center_tag is None:
        exit(print("Missing COST_CENTER_TAG"))

    if service_tag is None:
        exit(print("Missing SERVICE_TAG"))

    if created_by is None:
        exit(print("Missing CREATED_BY_TAG"))

    if resource_location is None:
        resource_location = "westeurope"

    if resource_group_name is None:
        # create Azure Resource Group
        resource_group_name_prefix = "researchit2"
        resource_group_name = (
            resource_group_name_prefix + "-" + unique_number + "-" + unique_id + "-rg"
        )
        resource_group_parameters = {
            "location": resource_location,
            "tags": {
                "costCenter": cost_center_tag,
                "service": service_tag,
                "createdBy": created_by,
            },
        }
        print(f"Creating Azure Resource Group {resource_group_name}.")
        create_azure_resource_group(
            resource_group_name, resource_group_parameters)

    # create Azure Key Vault
    key_vault_name = "kv" + unique_number
    print(f"Creating key vault {key_vault_name}.")
    create_key_vault(
        resource_group_name,
        key_vault_name,
        azure_tenant_id,
        azure_object_id,
        cost_center_tag,
        service_tag,
        created_by,
        resource_location
    )

    public_ip_address_name = "pip" + unique_number
    print(
        f"Creating an Azure Public IP address."
    )
    create_public_ip_prefix_ip_address(
        resource_group_name,
        public_ip_address_name,
        cost_center_tag,
        service_tag,
        created_by,
        resource_location
    )

    # deploy Azure Virtual Machine

    """
    "timestamp": "[parameters('customExtensionTimestamp')]"
    "protectedSettings": {
    "commandToExecute": "[parameters('customExtensionCommandToExecute')]",
    "fileUris": ["[parameters('customExtensionFileUris')]"]
    """
    custom_extension_timestamp = unique_number
    custom_extension_command_to_execute = "sh kilroy-was-here.sh"
    custom_extension_file_uris = "https://github.com/researchit2/create-linux-vm/blob/master/scripts/kilroy-was-here.sh"
    image_publisher = "Canonical"
    image_offer = "UbuntuServer"
    image_sku = "18.04-LTS"
    image_version = "latest"
    virtual_machine_deployment_template = "create-linux-vm-template.json"
    virtual_machine_location = resource_location
    network_interface_name = "nic" + unique_number
    network_security_group_name = "nsg" + unique_number
    virtual_network_name = "vnet" + unique_number
    virtual_machine_name = "vm" + unique_number
    virtual_machine_size = "Standard_D2s_v3"
    deployment_name = "deployment" + unique_number
    admin_user_name = "admin" + unique_number
    admin_password = generate_safe_password(32)

    print(
        f"Adding virtual machine {virtual_machine_name} credentials to the key vault {key_vault_name}."
    )
    create_secret_in_key_vault(
        resource_group_name, key_vault_name, admin_user_name, admin_password
    )

    print(f"Deploying virtual machine {virtual_machine_name}.")
    deploy_virtual_machine_from_arm_template(
        resource_group_name,
        virtual_machine_location,
        network_interface_name,
        network_security_group_name,
        virtual_network_name,
        virtual_machine_name,
        virtual_machine_size,
        admin_user_name,
        admin_password,
        custom_extension_timestamp,
        custom_extension_command_to_execute,
        custom_extension_file_uris,
        deployment_name,
        public_ip_address_name,
        subscription_id,
        cost_center_tag,
        service_tag,
        created_by,
        image_publisher,
        image_offer,
        image_sku,
        image_version,
        virtual_machine_deployment_template
    )


def get_storage_account_key(
    custom_extension_storage_account_resource_group_name,
    custom_extension_storage_account_name,
):
    "Fetch Azure Storage Account Key"
    credentials = get_azure_credentials(
        azure_tenant_id, azure_client_id, azure_secret_id
    )
    storage_resource = StorageManagementClient(credentials, subscription_id)
    storage_keys = storage_resource.storage_accounts.list_keys(
        custom_extension_storage_account_resource_group_name,
        custom_extension_storage_account_name,
        custom_headers=None,
        raw=False,
    )
    return storage_keys


def create_secret_in_key_vault(
    resource_group_name, key_vault_name, key_vault_secret_name, key_vault_secret_value
):
    "Create an Azure Key Vault Secret"
    credentials = get_azure_credentials(
        azure_tenant_id, azure_client_id, azure_secret_id
    )
    key_vault_data_plane_client = KeyVaultClient(credentials)
    key_vault_info = get_key_vault(resource_group_name, key_vault_name)

    try:
        key_vault_secret_bundle = key_vault_data_plane_client.set_secret(
            key_vault_info.properties.vault_uri,
            key_vault_secret_name,
            key_vault_secret_value,
        )
    except CloudError as ex:
        print(ex)


def get_key_vault(resource_group_name, key_vault_name):
    ""
    credentials = get_azure_credentials(
        azure_tenant_id, azure_client_id, azure_secret_id
    )
    key_vault_resource = KeyVaultManagementClient(credentials, subscription_id)
    try:
        key_vault_result = key_vault_resource.vaults.get(
            resource_group_name, key_vault_name, custom_headers=None, raw=False
        )
    except CloudError as ex:
        print(ex)
    return key_vault_result


def create_key_vault(
    resource_group_name,
    key_vault_name,
    azure_tenant_id,
    azure_object_id,
    cost_center_tag,
    service_tag,
    created_by,
    resource_location
):
    "create Azure Key Vault"
    credentials = get_azure_credentials(
        azure_tenant_id, azure_client_id, azure_secret_id
    )
    parameters = {
        "location": resource_location,
        "tags": {
            "costCenter": cost_center_tag,
            "service": service_tag,
            "createdBy": created_by,
        },
        "properties": {
            "sku": {"name": "standard"},
            "tenant_id": azure_tenant_id,
            "access_policies": [
                {
                    "object_id": azure_object_id,
                    "tenant_id": azure_tenant_id,
                    "permissions": {"keys": ["all"], "secrets": ["all"]},
                }
            ],
        },
    }
    key_vault_resource = KeyVaultManagementClient(credentials, subscription_id)
    try:
        create_the_keyvault = key_vault_resource.vaults.create_or_update(
            resource_group_name,
            key_vault_name,
            parameters,
            custom_headers=None,
            raw=False,
            polling=True,
        )
    except CloudError as ex:
        print(ex)
    create_the_keyvault.result()


def deploy_virtual_machine_from_arm_template(
    resource_group_name,
    virtual_machine_location,
    network_interface_name,
    network_security_group_name,
    virtual_network_name,
    virtual_machine_name,
    virtual_machine_size,
    admin_user_name,
    admin_password,
    custom_extension_timestamp,
    custom_extension_command_to_execute,
    custom_extension_file_uris,
    deployment_name,
    public_ip_address_name,
    subscription_id,
    cost_center_tag,
    service_tag,
    created_by,
    image_publisher,
    image_offer,
    image_sku,
    image_version,
    virtual_machine_deployment_template
):
    "Deploy Azure Virtual Machine with an ARM template file and adjustable parameters"
    credentials = get_azure_credentials(
        azure_tenant_id, azure_client_id, azure_secret_id
    )
    client_resource = ResourceManagementClient(credentials, subscription_id)

    deployment_template_path = os.path.join(
        os.path.dirname(
            __file__), "templates", virtual_machine_deployment_template
    )
    with open(deployment_template_path, "r") as deployment_template_file:
        deployment_template = json.load(deployment_template_file)

    deployment_parameters = {
        "location": virtual_machine_location,
        "networkInterfaceName": network_interface_name,
        "networkSecurityGroupName": network_security_group_name,
        "networkSecurityGroupRules": [
            {
                "name": "SSH",
                "properties": {
                    "priority": 301,
                    "protocol": "TCP",
                    "access": "Allow",
                    "direction": "Inbound",
                    "sourceAddressPrefix": "*",
                    "sourcePortRange": "*",
                    "destinationAddressPrefix": "*",
                    "destinationPortRange": "22",
                }
            }
        ],
        "subnetName": "default",
        "publicIpAddressId": "/subscriptions/"
        + subscription_id
        + "/resourceGroups/"
        + resource_group_name
        + "/providers/Microsoft.Network/publicIPAddresses/"
        + public_ip_address_name,
        "virtualNetworkName": virtual_network_name,
        "addressPrefixes": ["10.10.10.0/24"],
        "subnets": [
            {"name": "default", "properties": {"addressPrefix": "10.10.10.0/24"}}
        ],
        "virtualMachineName": virtual_machine_name,
        "osDiskType": "Premium_LRS",
        "virtualMachineSize": virtual_machine_size,
        "adminUsername": admin_user_name,
        "adminPassword": admin_password,
        "customExtensionTimestamp": custom_extension_timestamp,
        "customExtensionCommandToExecute": custom_extension_command_to_execute,
        "customExtensionFileUris": custom_extension_file_uris,
        "costCenter": cost_center_tag,
        "service": service_tag,
        "createdBy": created_by,
        "imagePublisher": image_publisher,
        "imageOffer": image_offer,
        "imageSku": image_sku,
        "imageVersion": image_version
    }

    deployment_parameters = {k: {"value": v}
                             for k, v in deployment_parameters.items()}

    deployment_properties = {
        "mode": DeploymentMode.incremental,
        "template": deployment_template,
        "parameters": deployment_parameters,
    }

    try:
        deployment_async_operation = client_resource.deployments.create_or_update(
            resource_group_name, str(deployment_name), deployment_properties
        )
    except CloudError as ex:
        print(ex)
    deployment_async_operation.wait()


def create_unique_number():
    "Create an unique number"
    epoch = time.time()
    unique_number = "%d" % (epoch)
    return unique_number


def create_uuid():
    "Create an Universally Unique Identifier"
    unique_id = uuid.uuid4()
    return unique_id


def generate_safe_password(password_length):
    "Generate safe passwords"
    safe_password = secrets.token_urlsafe(password_length)
    return safe_password


def create_azure_resource_group(resource_group_name, resource_group_parameters):
    "create an azure resource group"
    credentials = get_azure_credentials(
        azure_tenant_id, azure_client_id, azure_secret_id
    )
    client_resource = ResourceManagementClient(credentials, subscription_id)
    try:
        client_resource.resource_groups.create_or_update(
            resource_group_name, resource_group_parameters
        )
    except CloudError as ex:
        print(ex)
    return resource_group_name


def get_azure_credentials(azure_tenant_id, azure_client_id, azure_secret_id):
    "Fetch Azure Credentials"
    try:
        credentials = ServicePrincipalCredentials(
            client_id=azure_client_id, secret=azure_secret_id, tenant=azure_tenant_id
        )
    except CloudError as ex:
        print(ex)
    return credentials


def create_public_ip_prefix_ip_address(
    resource_group_name,
    public_ip_address_name,
    cost_center_tag,
    service_tag,
    created_by,
    resource_location
):
    "Create an Azure Public IP Prefix Public IP Address"
    credentials = get_azure_credentials(
        azure_tenant_id, azure_client_id, azure_secret_id
    )

    client_network = NetworkManagementClient(credentials, subscription_id)

    parameters = {
        "location": resource_location,
        "tags": {
            "costCenter": cost_center_tag,
            "service": service_tag,
            "createdBy": created_by,
        },
        "type": "PublicIPAddress",
        "sku": {"name": "Standard"},
        "public_ip_allocation_method": "Static",
        "public_ip_address_version": "IPv4"
    }

    try:
        create_public_ip_prefix = client_network.public_ip_addresses.create_or_update(
            resource_group_name,
            public_ip_address_name,
            parameters,
            custom_headers=None,
            raw=False,
            polling=True,
        )
    except CloudError as ex:
        print(ex)
    except:
        print("Error")


if __name__ == "__main__":
    main()

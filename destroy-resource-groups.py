import os
import time

from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network import NetworkManagementClient
from msrestazure.azure_exceptions import CloudError
# from azure.mgmt.network.v2019_02_01.models import PublicIPPrefix

azure_tenant_id = os.environ.get("AZURE_TENANT_ID")
azure_client_id = os.environ.get("AZURE_CLIENT_ID")
azure_secret_id = os.environ.get("AZURE_SECRET_ID")
subscription_id = os.environ.get("AZURE_SUBSCR_ID")
resource_group_name_prefix = os.environ.get("RESOURCE_GROUP_NAME_PREFIX")


def main():
    ""
    if azure_tenant_id is None:
        exit(print("Missing AZURE_TENANT_ID"))

    if azure_client_id is None:
        exit(print("Missing AZURE_CLIENT_ID"))

    if azure_secret_id is None:
        exit(print("Missing AZURE_SECRET_ID"))

    if subscription_id is None:
        exit(print("Missing AZURE_SUBSCR_ID"))

    if resource_group_name_prefix is None:
        exit(print("Missing RESOURCE_GROUP_NAME_PREFIX"))

    remove_azure_resource_group(resource_group_name_prefix)


def remove_azure_resource_group(resource_group_name_prefix):
    ""
    credentials = get_azure_credentials(
        azure_tenant_id, azure_client_id, azure_secret_id
    )
    client_resource = ResourceManagementClient(credentials, subscription_id)
    try:
        for item in client_resource.resource_groups.list():
            if item.name.startswith(resource_group_name_prefix):
                print(item.name)
                try:
                    print(f"Removing resource group {item.name}.")
                    remove_resource_group = client_resource.resource_groups.delete(
                        item.name
                    )
                    # print(remove_resource_group.result())
                    remove_resource_group.done()
                except CloudError as ex:
                    print(ex)
                except:
                    raise
            else:
                continue
    except CloudError as ex:
        print(ex)
    except:
        raise


def get_azure_credentials(azure_tenant_id, azure_client_id, azure_secret_id):
    credentials = ServicePrincipalCredentials(
        client_id=azure_client_id, secret=azure_secret_id, tenant=azure_tenant_id
    )
    return credentials


if __name__ == "__main__":
    main()

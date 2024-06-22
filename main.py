import os
import subprocess
import json
import re
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up Mistral AI API key
mistral_api_key = os.getenv("MISTRAL_API_KEY")
client = MistralClient(api_key=mistral_api_key)
model = "mistral-large-latest"

# Define the tools (functions) that PAMM can use
tools = [
    {
        "type": "function",
        "function": {
            "name": "install_package",
            "description": "Install a package using pip",
            "parameters": {
                "type": "object",
                "properties": {
                    "package_name": {
                        "type": "string",
                        "description": "The name of the package to install"
                    },
                    "version": {
                        "type": "string",
                        "description": "The version of the package to install (optional)"
                    }
                },
                "required": ["package_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_packages",
            "description": "List all installed packages",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_package",
            "description": "Update a package or all packages",
            "parameters": {
                "type": "object",
                "properties": {
                    "package_name": {
                        "type": "string",
                        "description": "The name of the package to update (optional, if not provided, update all packages)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remove_package",
            "description": "Remove a package using pip",
            "parameters": {
                "type": "object",
                "properties": {
                    "package_name": {
                        "type": "string",
                        "description": "The name of the package to remove"
                    }
                },
                "required": ["package_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_package_version",
            "description": "Get the version of an installed package",
            "parameters": {
                "type": "object",
                "properties": {
                    "package_name": {
                        "type": "string",
                        "description": "The name of the package to check"
                    }
                },
                "required": ["package_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "explain_package",
            "description": "Get information about a package using pip show",
            "parameters": {
                "type": "object",
                "properties": {
                    "package_name": {
                        "type": "string",
                        "description": "The name of the package to explain"
                    }
                },
                "required": ["package_name"]
            }
        }
    }
]


def main():
    print("Welcome to PAMM - Package AI Management Module")
    print("Type 'exit' to quit the program.")

    messages = [ChatMessage(role="system",
                            content="You are PAMM, an AI package manager assistant. Help users manage their Python packages.")]

    while True:
        user_input = input("pamm> ").strip()
        if user_input.lower() == 'exit':
            print("Thank you for using PAMM. Goodbye!")
            break

        messages.append(ChatMessage(role="user", content=user_input))

        # Step 2: Model generates function arguments
        response = client.chat(model=model, messages=messages, tools=tools, tool_choice="auto")

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)

            # Step 3: Execute function to obtain tool results
            result = execute_function(function_name, function_args)

            # Add the function call and result to the messages
            messages.append(response.choices[0].message)
            messages.append(ChatMessage(role="tool", name=function_name, content=result, tool_call_id=tool_call.id))

            # Step 4: Model generates final answer
            final_response = client.chat(model=model, messages=messages)
            print(final_response.choices[0].message.content)
        else:
            print(response.choices[0].message.content)

        messages.append(response.choices[0].message)


def execute_function(function_name, args):
    if function_name == "install_package":
        return install_package(**args)
    elif function_name == "list_packages":
        return list_packages()
    elif function_name == "update_package":
        return update_package(**args)
    elif function_name == "remove_package":
        return remove_package(**args)
    elif function_name == "get_package_version":
        return get_package_version(**args)
    elif function_name == "explain_package":
        return explain_package(**args)
    else:
        return json.dumps({"error": f"Unknown function {function_name}"})


def install_package(package_name, version=None):
    if version:
        package_spec = f"{package_name}=={version}"
    else:
        package_spec = package_name

    print(f"Installing {package_spec}...")
    result = subprocess.run(["pip", "install", package_spec], capture_output=True, text=True)
    return json.dumps({"output": result.stdout if result.returncode == 0 else f"Error: {result.stderr}"})


def list_packages():
    print("Listing installed packages:")
    result = subprocess.run(["pip", "list"], capture_output=True, text=True)
    return json.dumps({"output": result.stdout if result.returncode == 0 else f"Error: {result.stderr}"})


def update_package(package_name=None):
    if package_name:
        print(f"Updating {package_name}...")
        result = subprocess.run(["pip", "install", "--upgrade", package_name], capture_output=True, text=True)
    else:
        print("Updating all packages...")
        result = subprocess.run(
            ["pip", "list", "--outdated", "--format=freeze", "|", "cut", "-d", "=", "-f", "1", "|", "xargs", "-n1",
             "pip", "install", "-U"], capture_output=True, text=True, shell=True)

    return json.dumps({"output": result.stdout if result.returncode == 0 else f"Error: {result.stderr}"})


def remove_package(package_name):
    print(f"Removing {package_name}...")
    result = subprocess.run(["pip", "uninstall", package_name, "-y"], capture_output=True, text=True)
    return json.dumps({"output": result.stdout if result.returncode == 0 else f"Error: {result.stderr}"})


def get_package_version(package_name):
    try:
        result = subprocess.run(["pip", "show", package_name], capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if line.startswith('Version:'):
                    version = line.split(':')[1].strip()
                    return json.dumps({"version": version})
        return json.dumps({"error": f"Package {package_name} not found or error occurred."})
    except Exception as e:
        return json.dumps({"error": str(e)})


def explain_package(package_name):
    try:
        result = subprocess.run(["pip", "show", package_name], capture_output=True, text=True)
        if result.returncode == 0:
            return json.dumps({"output": result.stdout})
        return json.dumps({"error": f"Package {package_name} not found or error occurred."})
    except Exception as e:
        return json.dumps({"error": str(e)})


def detect_intent(user_input):
    # Detect if the user is asking for an explanation of a package
    explain_pattern = re.compile(r"what does (\w+) do|explain (\w+)", re.IGNORECASE)
    match = explain_pattern.match(user_input)
    if match:
        package_name = match.group(1) or match.group(2)
        return "explain_package", {"package_name": package_name}

    return None, {}


if __name__ == "__main__":
    main()

import os
import subprocess
import time
import logging

logging.basicConfig(level=logging.INFO)

REVERSE_PROXY_TARGETS = dict()


def read_nginx_config():
    """
    Reads Nginx configurations and extracts all domains and reverse proxy targets.

    Returns
    -------
    targets : set
        The set of found targets.
    domains : set
        The set of found domains.
    """
    targets = set()
    domains = set()
    config_dirs = ["/etc/nginx/sites-enabled", "/etc/nginx/conf.d"]

    for config_dir in config_dirs:
        if os.path.exists(config_dir):
            for filename in os.listdir(config_dir):
                filepath = os.path.join(config_dir, filename)
                with open(filepath, "r") as file:
                    for line in file:
                        # Extract reverse proxy targets using simple string check
                        if 'proxy_pass' in line:
                            parts = line.split()
                            if len(parts) > 1 and parts[1].startswith('http'):
                                targets.add(parts[1].strip(';'))

                        # Extract server_name (domains) using string methods
                        if 'server_name' in line:
                            parts = line.split()
                            if len(parts) > 1:
                                domains.update(parts[1:])  # Domains can be space-separated

    return targets, domains

def reconstruct_line(line):
    """
    Splits the line into parts and reconstructs it by removing comments.

    Parameters
    ----------
    line : str
        The line to reconstruct.

    Returns
    -------
    str
        The reconstructed line without comments.
    """
    parts = line.split()
    reconstructed = []
    for part in parts:
        if part.startswith("#"):
            break
        reconstructed.append(part)
    return " ".join(reconstructed)

def proxypass_target(line):
    """
    Extract the target of a ProxyPass directive.

    Parameters
    ----------
    line : str
        The line containing the ProxyPass directive.

    Returns
    -------
    str or None
        The extracted target URL or UNIX socket, or None if not found.
    """
    parts = line.split()
    for part in parts:
        # Handle if it contains a | character
        if "|" in part:
            part_1 = part.split("|")[0]
            part_2 = part.split("|")[1]
            
            return part_1.strip('"'), part_2.strip('"')
            

        # Check if part is a URL
        if part.startswith('"http'):
            return part.strip('"'), None

        # Check if part is a UNIX socket
        if part.startswith('"unix:'):
            return part.strip('"'), None

    return None, None

def read_apache_config():
    """Read apache2 configurations and extract all domains and reverse proxy targets."""
    targets = set()
    domains = set()
    config_dirs = ["/etc/apache2/sites-enabled", "/etc/apache2/conf-enabled"]
    infos = {}
    for config_dir in config_dirs:
        if os.path.exists(config_dir):
            for filename in os.listdir(config_dir):
                _info = {}
                filepath = os.path.join(config_dir, filename)
                with open(filepath, "r") as file:
                    in_virtual_host = False
                    for line in file:
                        in_comment = False

                        # Check if inside <VirtualHost> block
                        if line.strip().startswith("<VirtualHost"):
                            in_virtual_host = True
                            
                        if line.strip().startswith("#"):
                            in_comment = True
    
                        if in_virtual_host and not in_comment:     
                            line = reconstruct_line(line) # Remove comments
                            # Extract reverse proxy targets
                            if 'ProxyPass' in line:
                                target = proxypass_target(line)
                                _info["proxypass"] = target
                                targets.add(target)
                               
                            
                            # Extract ServerName and ServerAlias (domains)
                            if 'ServerName' in line:
                                parts = line.split()
                                if len(parts) > 1:
                                    name = parts[1].strip()
                                    _info["name"] = name
                                    domains.add(name)
                            
                            if 'ServerAlias' in line:
                                parts = line.split()
                                if len(parts) > 1:
                                    _info["alias"] = parts[1:]
                                    domains.update(parts[1:])  # Add all aliases

                        # End of <VirtualHost> block
                        if line.strip().startswith("</VirtualHost>"):
                            in_virtual_host = False
                            if "proxypass" in _info and _info["proxypass"]:
                                infos[_info["proxypass"][0]] = _info
                            

    return targets, domains, infos

def check_port_usage(host, port):
    """Check what is using a specific port."""
    try:
        pids = subprocess.run(
            ["sudo", "lsof", "-t", "-i", f"@{host}:{port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return pids.stdout.strip().split('\n')
    except Exception as e:
        return f"Error checking port {port} on {host}: {e}"

def check_unix_socket_usage(socket_path):
    """
    Check what is using a specific UNIX socket.

    Parameters
    ----------
    socket_path : str
        The path to the UNIX socket.

    Returns
    -------
    list of dict
        A list of dictionaries containing details of each process using the socket.
    """
    try:
        pids = subprocess.run(
            ["sudo", "lsof", "-t", socket_path],  # Use "-t" to get PIDs
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        return pids.stdout.strip().split('\n')
        
    except Exception as e:
        logging.error(f"Error checking UNIX socket {socket_path}: {e}")
        return []

def check_process_usage(process_name):
    """Check what is using a specific process name.

    Parameters
    ----------
    process_name : str
        The name of the process.

    Returns
    -------
    str
        The output of the pgrep command or an error message.
    """
    try:
        result = subprocess.run(
            ["pgrep", "-a", process_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return result.stdout.strip()
    except Exception as e:
        return f"Error checking process {process_name}: {e}"

def get_systemctl_service(pid):
    """
    Identify the systemctl service associated with a process.

    Parameters
    ----------
    pid : str
        The process ID.

    Returns
    -------
    str
        The parsed service name or an error message.
    """
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "status", f"{pid}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        result_ = result.stdout.strip()
        return parse_systemctl_service_status(result_)[0]
    except Exception as e:
        return f"Error finding service: {e}"

def parse_systemctl_service_status(status):
    """
    Parse the output of systemctl status to extract the service name and status.
    
    Parameters
    ----------
    status : str
        The output of the systemctl status command.
    
    Returns
    -------
    tuple
        A tuple containing the service name and status.
    """
    lines = status.split("\n")
    service_name = lines[0].split(" ")[1]
    service_status = lines[2].split(":")[1].strip() if len(lines) > 2 and ":" in lines[2] else "unknown"
    return service_name, service_status

def resolve_targets(targets):
    """
    Recursively analyze services running behind reverse proxies.
    
    Parameters
    ----------
    targets : set
        A set of target endpoints to resolve.
    
    Returns
    -------
    dict
        A dictionary containing details of each resolved target.
    """
    visited = set()
    details = {}
    processed_pids = set()

    while targets:
        logging.debug("Resolving targets: %s", targets)
        target = targets.pop()
        primary, failover = target

        if primary and failover:
            logging.warning("Failover target detected: %s", failover)
            visited.add(primary)
            target = primary
        else:
            target = primary
        logging.debug("Resolving target: %s", target)
        visited.add(target)

        if target.startswith("unix:"):
            logging.debug("UNIX socket detected: %s", target)
            socket_path = target[5:]
            usage_info = check_unix_socket_usage(socket_path)
        else:
            if target.startswith("http://"):
                target = target[7:]
            host, port = target.split(":") if ":" in target else (target, "80")
            usage_info = check_port_usage(host, port)

        systemctl_services = set()
        if isinstance(usage_info, list):
            for entry in usage_info:
                pid = entry
                
                if pid and isinstance(pid, str) and pid not in processed_pids:
                    service = get_systemctl_service(pid)
                    systemctl_services.add(service)
                    processed_pids.add(pid)
        else:
            logging.error("Unexpected usage_info format for target %s", target)

        details[target] = {
            "usage_info": usage_info,
            "systemctl_service": list(systemctl_services)
        }

        # Identify new targets from the processes
        if isinstance(usage_info, list):
            new_ports = [entry['name'].split(":")[1] for entry in usage_info if 'name' in entry and entry['name'].startswith("127.0.0.1:")]
            for new_port in new_ports:
                new_target = f"127.0.0.1:{new_port}"
                if new_target not in visited:
                    targets.add(new_target)

            new_sockets = [entry['name'][5:] for entry in usage_info if 'name' in entry and entry['name'].startswith("unix:")]
            for new_socket in new_sockets:
                new_target = f"unix:{new_socket}"
                if new_target not in visited:
                    targets.add(new_target)

    return details

def main():
    """
    Main entry point of the script. Reads Nginx and Apache configurations,
    resolves targets, and prints the results.
    """
    nginx_targets, nginx_domains = read_nginx_config()
    apache_targets, apache_domains, infos = read_apache_config()


    logging.info("Found nginx reverse proxy targets.")
    logging.info("Found nginx domains.")
    logging.info("Found apache2 reverse proxy targets.")
    logging.info("Found apache2 domains.")

    all_targets = nginx_targets.union(apache_targets)
    all_domains = nginx_domains.union(apache_domains)

    if not all_targets and not all_domains:
        logging.info("No reverse proxy targets or domains found.")
        return
    
    print("Resolving targets...")
    resolved = resolve_targets(all_targets)

    for target, info in resolved.items():
        print(f"[Target: {target}]")
        print(f"PIDs: {info['usage_info']}")
        print(f"Systemctl Service: {info['systemctl_service']}")
        # Print associated domains
        is_http = target.endswith("/")
        target = "http://" + target if is_http else target
#        if is_http:
        associated_domains = []
        if target in infos:
            if "alias" in infos[target]:
                associated_domains = infos[target]["alias"]
            associated_domains.append(infos[target]["name"])
           
            
        print(f"Associated Domains: {associated_domains}")
        print()

    # Display all domains served
    print("All served domains:")
    for domain in all_domains:
        print("-", domain)

if __name__ == "__main__":
    main()

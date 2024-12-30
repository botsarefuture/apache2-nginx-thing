# Proxy Target Resolver

This Python script reads the Nginx and Apache configuration files to extract reverse proxy targets and domains. It then checks for any services that are using the identified targets and provides detailed information about those services.

## Features

- **Read Nginx and Apache configurations:** The script parses the reverse proxy targets (`proxy_pass` and `ProxyPass` directives) and domains (`server_name` and `ServerAlias` directives) from Nginx and Apache configuration files.
  
- **Identify services running behind reverse proxies:** It resolves the services running behind the reverse proxy targets, including both HTTP and UNIX sockets.

- **Port and socket usage check:** The script checks which processes are using specific ports or UNIX sockets, helping identify the services running on the server.

- **Systemd service mapping:** For each process using the reverse proxy target, the script attempts to identify the associated systemd service.

## Requirements

- Python 3.x
- Required libraries: `os`, `subprocess`, `time`, `logging`

## Installation

1. Clone the repository or download the script file.
2. Ensure you have the necessary permissions to access the configuration files of Nginx and Apache (usually requires root privileges).
3. Install Python 3 and ensure `subprocess` is available.
4. You may need `lsof` to check for port and UNIX socket usage. Ensure it is installed on your system.

## Configuration

Ensure that Nginx and Apache configuration files are located in the standard directories (`/etc/nginx/sites-enabled`, `/etc/nginx/conf.d`, `/etc/apache2/sites-enabled`, `/etc/apache2/conf-enabled`) or adjust the `config_dirs` variables in the `read_nginx_config` and `read_apache_config` functions accordingly.

## Usage

### 1. Run the script:

```bash
python proxy_target_resolver.py
```

### 2. The script will:
- Parse Nginx and Apache configuration files to identify reverse proxy targets and domains.
- Check which processes are using the identified targets, whether they are running on specific ports or UNIX sockets.
- Try to resolve the associated systemd service for each process.
- Output the results in the terminal with detailed information about each target.

## Example Output

```
Resolving targets...
Found nginx reverse proxy targets.
Found nginx domains.
Found apache2 reverse proxy targets.
Found apache2 domains.
Resolving target: http://example.com:8080
UNIX socket detected: /var/run/example.sock
Systemd service: apache2
...
```

## Functions

### `read_nginx_config()`
Reads Nginx configuration files to extract reverse proxy targets and domains.

### `reconstruct_line()`
Reconstructs a line from the configuration file by removing comments.

### `proxypass_target()`
Extracts the target of a `ProxyPass` directive from Apache configuration.

### `read_apache_config()`
Reads Apache configuration files to extract reverse proxy targets and domains.

### `check_port_usage()`
Checks for processes using a specific port.

### `check_unix_socket_usage()`
Checks for processes using a specific UNIX socket.

### `check_process_usage()`
Checks for processes using a specific process name.

### `get_systemctl_service()`
Identifies the systemd service associated with a given process ID.

### `resolve_targets()`
Recursively resolves services running behind reverse proxy targets and identifies new targets.

## Logging

The script uses Python’s built-in logging module to log information at different levels. By default, logging is set to `INFO`, but you can adjust the logging level as needed.

```python
logging.basicConfig(level=logging.DEBUG)  # For detailed debug output
```

## Contributing

Feel free to fork the repository, submit issues, or open pull requests to contribute improvements or fixes.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
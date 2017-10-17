
# Library imports
import os, socket, struct, time

# Module exceptions
class HostUnreachable(Exception): pass
class ReplyTimeout(Exception): pass
class BadReply(Exception): pass
class HostLookupFailed(Exception): pass

def ping(dest, timeout=1):
    """
    Blocking ping function
    :param dest: Destination host string (ip or www)
    :param timeout: Seconds to wait for a response being raising a Timeout exception
    :return: 
    """

    # Open an socket with the ICMP protocol, and set the timeout
    sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    sock.settimeout(timeout)

    # Attempt to resolve the destination host
    dest_host = __resolve_host(dest)

    # Form the ICMP packet, including our process ID
    packet = __pack_icmp(dest_host, os.getpid())

    # Try to send the ping packet
    try: sock.sendto(packet, (dest_host, 1))

    # Catch get address info exception, and raise as host lookup failure
    except socket.gaierror: pass #raise HostLookupFailed

    # Resurrect any other exceptions
    except: raise

    # Try and receive the reply
    try: recv_data, addr = sock.recvfrom(1024)

    # Re-raise a socket timeout as a ReplyTimeout
    except socket.timeout: raise ReplyTimeout

    # Re-raise any other exceptions
    except: raise

    # Grab the time now (received time)
    received_time = time.time()

    # Unpack the ICMP packet, and extract the time of launch
    launch_time = __unpack_icmp(recv_data, os.getpid())

    # Return the time of flight (difference between launch and receive time)
    return received_time - launch_time


def __unpack_icmp(obj, PID):

    # Slice the header out
    icmp_header = obj[20:28]

    # Unpack the header
    type, code, checksum, packetID, sequence = struct.unpack("bbHHh", icmp_header)

    # If its not valid a ping reply throw an exception
    if code != 0 or type != 0 or packetID != PID:
        raise BadReply

    # Unpack and return the ICMP payload
    return struct.unpack("d", obj[28:28 + 8])[0]


def __pack_icmp(host, PID):

    # Set ICMP header vars
    type = 8
    code = 0
    checksum = 0
    ident = PID
    flags = 1

    # Pack the icmp header
    header = struct.pack("bbHHh", type, code, checksum, ident, flags)

    # Pack the icmp payload
    data = bytes( (192 - 8) * "Q", "ascii" )
    data = struct.pack("d", time.time()) + data

    # Calculate the checksum, and repack the header with it
    checksum = __calc_ip_checksum(header + data)
    header = struct.pack("bbHHh", type, code, checksum, ident, flags)

    # Return the completed packet
    return header + data


def __calc_ip_checksum(data, size=0):

    # Initialise byte index and checksum to zero
    cksum = 0
    byte_index = 0

    # If size is zero (argument omitted), use the length of the data
    size = size if size > 0 else len(data)

    # The main loop adds up each set of 2 bytes. They are first converted to strings and then concatenated
    # together, converted to integers, and then added to the sum.
    while size > 1:
        cksum += int((str("%02x" % (data[byte_index],)) +
                      str("%02x" % (data[byte_index + 1],))), 16)
        size -= 2
        byte_index += 2

    # This accounts for a situation where the header is odd
    if size:
        cksum += data[byte_index]

    # Shift, mask, shift, invert return
    cksum = (cksum >> 16) + (cksum & 0xffff)
    cksum += (cksum >> 16)
    cksum = (~cksum) & 0xFFFF
    return socket.htons(cksum)


def __resolve_host(dest):

    # Try and parse it as an IP address, returning the original string if it doesn't throw an error
    try: return dest if socket.inet_aton(dest) else ""

    # Catch socket error (not a valid IP address)
    except socket.error:

        # Try a DNS lookup for the host, returning the result
        try: return socket.gethostbyname_ex(dest)[0]

        # Catch socket error (not valid ip and host lookup failed)
        except socket.error:
            raise HostLookupFailed

        # Catch and re-raise any other exceptions
        except: raise

    # Catch and re-raise any other exceptions
    except: raise


if __name__ == "__main__":


    print(ping("139.130.4.5"))
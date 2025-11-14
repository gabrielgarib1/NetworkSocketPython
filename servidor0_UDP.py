

import socket


my_ip='127.0.0.1'    #Qualquer um, usamos o local
my_port=5000    #port to listen on

udp=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp.bind((my_ip,my_port))

max_message_size=1   #in megabytes
received_data, addr=udp.recvfrom(2**(8*max_message_size))  


print("Message: ", received_data.decode(), "| received from:", addr)

udp.close()
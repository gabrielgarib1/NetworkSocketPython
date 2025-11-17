# **Reliable File Transfer over UDP**

This project implements a reliable file transfer protocol over UDP, simulating key TCP functionalities such as a 3-way handshake, sequence numbers, acknowledgments (ACKs), timeouts, and retransmissions.

## **Protocol Overview**

The system uses a client and a server that communicate via UDP. Reliability is achieved through a Stop-and-Wait ARQ mechanism:

1. **Handshake:** The client initiates a connection with a SYN packet. The server responds with SYN+ACK, and the client finalizes with an ACK.  
2. **Data Transfer:** The client sends data packets sequentially. For each packet, it waits for a corresponding ACK from the server before sending the next one.  
3. **Reliability:** If an ACK is not received within the defined TIMEOUT, the client retransmits the packet. The server handles duplicate packets (by resending the ACK) and corrupted packets (by discarding them).  
4. **Teardown:** The client sends a FIN packet to close the connection, and both sides exchange final ACKs.

## **Project Files**

* server\_gem.py: The server script. It listens for connections, manages the handshake, receives the file, and saves it locally.  
* client\_gem.py: The client script. It initiates the connection, reads a file from disk, and sends it to the server packet by packet, managing retransmissions.  
* shared\_config.py: Shared configuration module. Defines constants (port, host, buffer size, SYN/ACK/FIN flags) and utility functions for creating, packing, and verifying packets (make\_packet, unpack\_packet, verify\_checksum).  
* create\_dummy\_file.py: Utility script to generate a test file (test\_file.txt) of arbitrary size.

## **How to Run**

### **1\. Start the Server**

Open a terminal and run the server:  
python3 server\_gem.py

### **2\. Generate a Test File (Optional)**

If you don't have a file to send, open a second terminal and create one:  
python3 create\_dummy\_file.py

This will create a file named test\_file.txt.

### **3\. Send the File**

In the second terminal, run the client to send the file:  
python3 client\_gem.py test\_file.txt

### **4\. Verify the Result**

The server will save the received file as received\_file.txt (or received\_file1.txt, etc., if the name already exists). You can verify the integrity of the transfer:  
**Linux/macOS:**  
diff test\_file.txt received\_file.txt

**Windows:**  
fc /b test\_file.txt received\_file.txt

If no output is displayed, the files are identical.

## **Server Simulation Modes**

The server can be started with arguments to test the protocol's robustness:

* **Mode 0 (Normal):** python3 server\_gem.py 0  
  * Default behavior, no induced faults.  
* **Mode 1 (Single Failure):** python3 server\_gem.py 1  
  * The server will intentionally ignore (drop) the second data packet it receives, forcing the client to time out and retransmit.  
* **Mode 2 (Fuzzing):** python3 server\_gem.py 2  
  * The server will randomly drop or corrupt incoming packets to simulate an unstable network.

from pyroute2.common import map_namespace
from pyroute2.netlink import NLMSG_DONE
from pyroute2.netlink.nlsocket import Marshal

from . import ConnectorSocket, cn_msg

CN_IDX_W1 = 0x1

W1_SLAVE_ADD = 0x0
W1_SLAVE_REMOVE = 0x1
W1_MASTER_ADD = 0x2
W1_MASTER_REMOVE = 0x3
W1_MASTER_CMD = 0x4
W1_SLAVE_CMD = 0x5
W1_LIST_MASTERS = 0x6

(W1_BY_NAMES, W1_BY_IDS) = map_namespace('W1_', globals())

W1_CMD_READ = 0
W1_CMD_WRITE = 1
W1_CMD_SEARCH = 2
W1_CMD_ALARM_SEARCH = 3
W1_CMD_TOUCH = 4
W1_CMD_RESET = 5
W1_CMD_SLAVE_ADD = 6
W1_CMD_SLAVE_REMOVE = 7
W1_CMD_LIST_SLAVES = 8
W1_CMD_MAX = 9

CN_W1_IDX = 0x3
CN_W1_VAL = 0x1


class w1_event_base(cn_msg):
    fields = cn_msg.fields + (
        ('type', 'B'), #__u8
        ('status', 'B'), #__u8
        ('len', 'H'), #__u16
    )

    def decode(self):
        super().decode()
        self['event'] = W1_BY_IDS.get(self['type'], 'UNDEFINED')


class w1_slave_add(w1_event_base):
    fields = w1_event_base.fields + (
        ('id', '8B'),
    )


class w1_slave_remove(w1_event_base):
    fields = w1_event_base.fields + (
        ('id', '8B'),
    )


class w1_master_add(w1_event_base):
    fields = w1_event_base.fields + (
        ('id', 'I'),
        ('reserved', 'I'),
    )


class w1_master_remove(w1_event_base):
    fields = w1_event_base.fields + (
        ('id', 'I'),
        ('reserved', 'I'),
    )

'''
class w1_event_control(cn_msg):
    fields = cn_msg.fields + (('action', 'I'),)
'''

class w1_cmd_base(w1_event_base):
    fields = w1_event_base.fields + (
        ('id', 'I'),
        ('reserved', 'I'),
    )

class W1EventMarshal(Marshal):
    key_format = 'B'
    key_offset = 36
    error_type = -1
    msg_map = {
        W1_SLAVE_ADD: w1_slave_add,
        W1_SLAVE_REMOVE: w1_slave_remove,
        W1_MASTER_ADD: w1_master_add,
        W1_MASTER_REMOVE: w1_master_remove,
    }


class W1EventSocket(ConnectorSocket):
    def __init__(self, fileno=None):
        super().__init__(fileno=fileno)
        self.marshal = W1EventMarshal()

    #https://github.com/bioothod/w1/blob/master/w1d.c
    def bind(self):
        return super().bind(groups=23)

'''
    def control(self, listen):
        msg = proc_event_control()
        msg['action'] = (
            PROC_CN_MCAST_LISTEN if listen else PROC_CN_MCAST_IGNORE
        )
        msg['idx'] = CN_W1_IDX
        msg['val'] = CN_W1_VAL
        msg['len'] = 4  # FIXME payload length calculation
        msg_type = NLMSG_DONE
        self.put(msg, msg_type, msg_flags=0, msg_seq=0)
        return tuple(self.get(msg_seq=-1))
'''


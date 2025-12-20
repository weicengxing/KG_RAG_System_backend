import time
import threading

class SnowflakeGenerator:
    def __init__(self, machine_id=1, datacenter_id=1):
        self.machine_id = machine_id
        self.datacenter_id = datacenter_id
        self.sequence = 0
        
        self.twepoch = 1288834974657  # 起始时间戳 (2010-11-04)
        
        self.machine_id_bits = 5
        self.datacenter_id_bits = 5
        self.sequence_bits = 12
        
        self.max_machine_id = -1 ^ (-1 << self.machine_id_bits)
        self.max_datacenter_id = -1 ^ (-1 << self.datacenter_id_bits)
        self.sequence_mask = -1 ^ (-1 << self.sequence_bits)
        
        self.machine_id_shift = self.sequence_bits
        self.datacenter_id_shift = self.sequence_bits + self.machine_id_bits
        self.timestamp_left_shift = self.sequence_bits + self.machine_id_bits + self.datacenter_id_bits
        
        self.last_timestamp = -1
        self.lock = threading.Lock()

    def _current_timestamp(self):
        return int(time.time() * 1000)

    def next_id(self) -> str:
        """生成唯一ID，返回字符串格式"""
        with self.lock:
            timestamp = self._current_timestamp()

            if timestamp < self.last_timestamp:
                raise Exception("Clock moved backwards. Refusing to generate id")

            if self.last_timestamp == timestamp:
                self.sequence = (self.sequence + 1) & self.sequence_mask
                if self.sequence == 0:
                    while timestamp <= self.last_timestamp:
                        timestamp = self._current_timestamp()
            else:
                self.sequence = 0

            self.last_timestamp = timestamp

            # 生成 64位 ID
            id_val = ((timestamp - self.twepoch) << self.timestamp_left_shift) | \
                     (self.datacenter_id << self.datacenter_id_shift) | \
                     (self.machine_id << self.machine_id_shift) | \
                     self.sequence
            
            return str(id_val)

# 初始化单例
id_generator = SnowflakeGenerator(machine_id=1, datacenter_id=1)

# 这是一个分布式唯一ID生成器，基于 Twitter Snowflake 算法。
# 核心功能：
# 在分布式系统中生成 全局唯一、趋势递增 的64位整数ID，通过组合时间戳、
# 、机器ID、数据中心ID
# 和序列号来保证唯一性，每毫秒最多生成4096个ID，无需依赖数据库，线程安全。

#
#数据中心ID (datacenter_id) 是用来标识不同物理机房或云服务区域的编号
#每个机房内还可以有多台服务器，用 machine_id 区分
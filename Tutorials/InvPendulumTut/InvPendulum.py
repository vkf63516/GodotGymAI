"""
Classic cart-pole system implemented by Rich Sutton et al.
Copied from http://incompleteideas.net/sutton/book/code/pole.c
permalink: https://perma.cc/C9ZM-652R
"""

import math

import subprocess
import torch
import _GodotEnv
import numpy as np
import atexit
import os

import gym
from gym import spaces

class InvPendulumEnv(gym.Env):
	"""
	Description:
		Standard inverted pendulum environment but for the discrete action space
	Observation: 
		Type: Box(3)
		Num	Observation     
		0	Cos(theta)      
		1	Sin(theta)      
		2	Angular velocity
		
	Actions:
		Type: [Continuous(1)]
		Num	Action
		0	Torque
		
	Reward:
		var n_theta = fmod((theta + PI), (2*PI)) - PI
		reward = (n_theta*n_theta + .1*angular_velocity*angular_velocity)
	Starting State:
		Initialized with random angle
	Episode Termination:
		Terminated after 10s
	"""

	def __init__(self, exec_path, env_path, render=False):
		self.handle = "environment"
		self.mem = _GodotEnv.SharedMemoryTensor(self.handle)
		self.sem_act = _GodotEnv.SharedMemorySemaphore("sem_action", 0)
		self.sem_obs = _GodotEnv.SharedMemorySemaphore("sem_observation", 0)

		#Important: if this process is called with subprocess.PIPE, the semaphores will be stuck in impossible combination
		with open("stdout.txt","wb") as out, open("stderr.txt","wb") as err:
			if render:
				self.process = subprocess.Popen([exec_path, "--path", os.path.abspath(env_path), "--handle", self.handle], stdout=out, stderr=err)
			else:
				self.process = subprocess.Popen([exec_path, "--path", os.path.abspath(env_path),"--disable-render-loop", "--handle", self.handle], stdout=out, stderr=err)
		
		#Array to manipulate the state of the simulator
		self.env_action = torch.zeros(2, dtype=torch.int, device='cpu')
		self.env_action[0] = 0	#1 = reset
		self.env_action[1] = 0	#1 = exit

		#Example of agent action
		self.agent_action = torch.zeros(1, dtype=torch.float, device='cpu')

		self.max_torque = 8.0
		self.max_speed = 8

		high = np.array([1., 1., self.max_speed])
		self.action_space = spaces.Box(low=-self.max_torque, high=self.max_torque, shape=(1,), dtype=np.float32)
		self.observation_space = spaces.Box(low=-high, high=high, dtype=np.float32)

		atexit.register(self.close)

	def seed(self, seed=None):
		pass

	def step(self, action):
		# print("Sending action")
		action = torch.clamp(action, min=-self.max_torque, max=self.max_torque)
		self.mem.sendFloat("agent_action", action)
		self.mem.sendInt("env_action", self.env_action)
		self.sem_act.post()
		# print("Waiting for observation")
		
		self.sem_obs.wait()
		# print("Reading observation")
		observation = self.mem.receiveFloat("observation")
		reward = self.mem.receiveFloat("reward")
		done = self.mem.receiveInt("done")
		# print("Read observation")

		clamp_speed = torch.clamp(observation[2], min=-self.max_speed, max=self.max_speed)
		observation[2] = clamp_speed

		return observation, reward.item(), done.item(), None
		
	def reset(self):
		# print("Sending reset action")
		env_action = torch.tensor([1, 0], device='cpu', dtype=torch.int)
		self.mem.sendFloat("agent_action", self.agent_action)
		self.mem.sendInt("env_action", env_action)
		self.sem_act.post()
		# print("Sent reset action")

		self.sem_obs.wait()
		# print("Reading observation")
		observation = self.mem.receiveFloat("observation")
		reward = self.mem.receiveFloat("reward")
		done = self.mem.receiveInt("done")
		# print("Read observation")
		return observation
		

	def render(self, mode='human'):
		pass

	def close(self):
		self.process.terminate()
		print("Terminated")


if __name__=='__main__':
	import gym
	from gym import spaces
	from gym.utils import seeding
	from matplotlib import pylab as plt
	from gymPendulum import PendulumEnv
	# env = gym.make("Pendulum-v0")
	env = PendulumEnv()
	env.reset()
	# env.env.state = np.array([0.0, 1])

	GODOT_BIN_PATH = "InvPendulum/InvPendulum.server.x86_64"
	env_abs_path = "InvPendulum/InvPendulum.server.pck"
	env_my = InvPendulumEnv(exec_path=GODOT_BIN_PATH, env_path=env_abs_path)
	env_my.reset()

	gym_obs = []
	gym_rew = []
	my_obs = []
	my_rew = []
	for i in range(1000):
		obs_my, rew_my, done, _ = env_my.step(torch.tensor([8.0]))
		obs, rew, done, _ = env.step(np.array([2.0]))
		env.render()
		gym_obs.append(obs)
		gym_rew.append(rew)
		my_obs.append(obs_my)
		my_rew.append(rew_my)
	
	env_my.close()
	
	gym_obs = np.array(gym_obs)
	gym_rew = np.array(gym_rew)
	my_obs = torch.stack(my_obs, dim=0).numpy()
	my_rew = np.array(my_rew)

	plt.subplot(1,4,1)
	plt.plot(gym_rew, label='Gym rewards')
	plt.plot(my_rew, label='My rewards')
	plt.subplot(1,4,2)
	plt.plot(gym_obs[:,0], label='gym obs0')
	plt.plot(my_obs[:,0], label='my obs0')
	plt.subplot(1,4,3)
	plt.plot(gym_obs[:,1], label='gym obs1')
	plt.plot(my_obs[:,1], label='my obs1')
	plt.subplot(1,4,4)
	plt.plot(gym_obs[:,2], label='gym obs2')
	plt.plot(my_obs[:,2], label='my obs2')
	plt.legend()
	plt.show()
from setuptools import find_packages, setup

package_name = 'trn_consumer'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='akhil',
    maintainer_email='178921788+akhilgolepu@users.noreply.github.com',
    description='Planner stub that waits when confidence is low',
    license='MIT',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'consumer_node = trn_consumer.consumer_node:main',
        ],
    },
)

from setuptools import find_packages, setup

package_name = 'trn_matcher'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    package_data={package_name: ['matcher_frozen.json']},
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='akhil',
    maintainer_email='178921788+akhilgolepu@users.noreply.github.com',
    description='Tile store, terrain matching, absolute fix with diagnostics',
    license='MIT',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'matcher_node = trn_matcher.matcher_node:main',
        ],
    },
)

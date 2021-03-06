from setuptools import setup


setup(
    name="aiowebsocketclient",
    version="0.0.5",
    url="",
    license="MIT",
    author="davebshow",
    author_email="davebshow@gmail.com",
    description="WebSocket client connection manager for aiohttp",
    long_description=open("README.txt").read(),
    packages=["aiowebsocketclient", "tests"],
    install_requires=[
        "aiohttp==0.18.4"
    ],
    test_suite="tests",
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3 :: Only'
    ]
)

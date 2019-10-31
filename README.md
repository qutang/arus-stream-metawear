`arus-stream-metawear` package is a plugin for [`arus`](https://qutang.github.io/arus/) package. It provides extra functionality to stream data from metawear devices in real-time.

### Get started

#### Prerequistes

```bash
python >= 3.6
```

##### Linux

```bash
libbluetooth-dev
libboost-all-dev
bluez
```

##### Windows

```bash
Visual Studio C++ SDK
Windows SDK (10.0.16299.0)
Windows SDK (10.0.17763.0)
```

#### Installation

Because one of the dependency is from git repository, pypi package is not available. Users should install directly from git repository.

```bash
> pip install git+https://github.com/qutang/arus-stream-metawear.git#egg=arus-stream-metawear
```

Or `pipenv`

```bash
> pipenv install git+https://github.com/qutang/arus-stream-metawear.git#egg=arus-stream-metawear
```

Or `poetry`

```bash
> poetry add --git https://github.com/qutang/arus-stream-metawear.git arus-stream-metawear
```


### Development

#### Prerequists

```bash
python >= 3.6
poetry >= 0.12.17
```

#### Set up development environment

```bash
> git clone https://github.com/qutang/arus-stream-metawear.git
> cd arus-stream-metawear
> poetry install
```
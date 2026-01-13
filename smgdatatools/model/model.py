from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, backref

from smgdatatools.etl.lib import calculate_chunk_idx

Base = declarative_base()


class Store(Base):
    __tablename__ = "store"

    id = Column("id", Integer, primary_key=True)
    name = Column("name", String(500))
    size = Column("size", Float)

    variables = relationship("Variable", back_populates="store")
    attrs = relationship("GlobalAttribute")

    def __repr__(self):
        return f"Store(id={self.id!r}, name={self.name!r})"


class Variable(Base):
    __tablename__ = "variable"

    id = Column("id", Integer, primary_key=True)
    name = Column("name", String(500))
    dtype = Column("dtype", String(5))
    fillvalue = Column("fillvalue", Float)

    store_id = Column(Integer, ForeignKey("store.id"))
    store = relationship("Store", back_populates="variables")

    compressor_id = Column(Integer, ForeignKey("compressor.id"))
    compressor = relationship("Compressor", backref=backref("compressor", uselist=False))

    dimensions = relationship("Dimension")
    chunks = relationship("Chunk")
    scales = relationship("Scale")
    attrs = relationship("Attribute")
    filters = relationship("Filter")

    def calculate_chunk_idx(self, cidx):
        return calculate_chunk_idx(self, cidx)

    def __repr__(self):
        return f"Variable(id={self.id!r}, " \
               f"name={self.name!r}, " \
               f"dtype={self.dtype!r}, " \
               f"store_id={self.store_id!r})"


class Dimension(Base):
    __tablename__ = "dimension"

    id = Column("id", Integer, primary_key=True)
    index = Column("index", Integer)
    size = Column("size", Integer)
    chunk_count = Column("chunk_count", Integer)
    variable_id = Column(Integer, ForeignKey("variable.id"))
    variable = relationship("Variable", back_populates="dimensions")

    scales = relationship("Scale")
    chunk_shapes = relationship("ChunkShape")

    def __repr__(self):
        return f"Dimension(id={self.id!r}, " \
               f"index={self.index!r}, " \
               f"size={self.size!r}, " \
               f"chunk_count={self.chunk_count!r}, " \
               f"variable_id={self.variable_id!r})"


class Filter(Base):
    __tablename__ = "filter"

    id = Column("id", Integer, primary_key=True)

    variable_id = Column(Integer, ForeignKey("variable.id"))
    variable = relationship("Variable", back_populates="filters")

    properties = relationship("FilterProperty")

    def __repr__(self):
        return f"Filter(id={self.id!r}, " \
               f"variable_id={self.variable_id!r})"


class FilterProperty(Base):
    __tablename__ = "filter_properties"

    id = Column("id", Integer, primary_key=True)
    name = Column("name", String(100))
    value = Column("value", String(1000))

    filter_id = Column(Integer, ForeignKey("filter.id"))
    filter = relationship("Filter", back_populates="properties")

    def __repr__(self):
        return f"FilterProperty(id={self.id!r}, " \
               f"name={self.name!r}, " \
               f"value={self.value!r}), " \
               f"filter_id={self.filter_id!r})"


class Compressor(Base):
    __tablename__ = "compressor"

    id = Column("id", Integer, primary_key=True)

    properties = relationship("CompressorProperty")

    def __repr__(self):
        return f"Compressor(id={self.id!r}"


class CompressorProperty(Base):
    __tablename__ = "compressor_properties"

    id = Column("id", Integer, primary_key=True)
    name = Column("name", String(100))
    value = Column("value", String(1000))

    compressor_id = Column(Integer, ForeignKey("compressor.id"))
    compressor = relationship("Compressor", back_populates="properties")

    def __repr__(self):
        return f"CompressorProperty(id={self.id!r}, " \
               f"name={self.name!r}, " \
               f"value={self.value!r}), " \
               f"compressor_id={self.compressor_id!r})"


class GlobalAttribute(Base):
    __tablename__ = "global_attribute"

    id = Column("id", Integer, primary_key=True)
    name = Column("name", String(100))
    value = Column("value", String(1000))

    store_id = Column(Integer, ForeignKey("store.id"))
    store = relationship("Store", back_populates="attrs")

    def __repr__(self):
        return f"GlobalAttribute(id={self.id!r}, " \
               f"name={self.name!r}, " \
               f"value={self.value!r}), " \
               f"store_id={self.store_id!r})"


class Attribute(Base):
    __tablename__ = "attribute"

    id = Column("id", Integer, primary_key=True)
    name = Column("name", String(100))
    value = Column("value", String(1000))

    variable_id = Column(Integer, ForeignKey("variable.id"))
    variable = relationship("Variable", back_populates="attrs")

    def __repr__(self):
        return f"Attribute(id={self.id!r}, " \
               f"name={self.name!r}, " \
               f"value={self.value!r}), " \
               f"variable_id={self.variable_id!r})"


class Scale(Base):
    __tablename__ = "scale"

    id = Column("id", Integer, primary_key=True)
    name = Column("name", String(50))
    dimension_id = Column(Integer, ForeignKey("dimension.id"))
    dimension = relationship("Dimension", back_populates="scales")
    variable_id = Column(Integer, ForeignKey("variable.id"))
    variable = relationship("Variable", back_populates="scales")

    def __repr__(self):
        return f"Scale(id={self.id!r}, " \
               f"name={self.name!r}, " \
               f"dimension_id={self.dimension_id!r}, " \
               f"variable_id={self.variable_id!r})"


class Chunk(Base):
    __tablename__ = "chunk"

    id = Column("id", Integer, primary_key=True)
    location = Column("location", Integer)
    size = Column("size", Integer)
    index = Column("index", Integer)

    variable_id = Column(Integer, ForeignKey("variable.id"))
    variable = relationship("Variable", back_populates="chunks")

    def __repr__(self):
        return f"Chunk(id={self.id!r}, " \
               f"index={self.index!r}, " \
               f"size={self.size!r}, " \
               f"location={self.location!r}, " \
               f"variable_id={self.variable_id!r})"


class ChunkShape(Base):
    __tablename__ = "chunkshape"

    id = Column("id", Integer, primary_key=True)
    shape = Column("shape", Integer)
    index = Column("index", Integer)

    dimension_id = Column(Integer, ForeignKey("dimension.id"))
    dimension = relationship("Dimension", back_populates="chunk_shapes")

    def __repr__(self):
        return f"ChunkShape(id={self.id!r}, " \
               f"shape={self.shape!r}, " \
               f"index={self.index!r}, " \
               f"dimension_id={self.dimension_id!r})"

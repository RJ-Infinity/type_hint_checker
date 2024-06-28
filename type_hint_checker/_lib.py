import typing
from typing import Any, TypeAliasType, TypeVar, ForwardRef, Literal, Self
from typing import LiteralString, Never, NoReturn, NewType, _GenericAlias
from typing import _SpecialGenericAlias, Generic, _TypedDictMeta, _UnionGenericAlias
from typing import _LiteralGenericAlias, _AnnotatedAlias, _CallableType
from typing import _CallableGenericAlias, Optional
from types import UnionType, GenericAlias, NoneType, FunctionType, BuiltinFunctionType
import inspect
from inspect import Parameter
from dataclasses import InitVar
from collections import abc
import sys

# TODO: check bellow to see if it they are GenericAliases when they are stable
# ReadOnly
# TypeIs

# it may seem we dont handle some typing objects but many of them end up becoming
# GenricAlias's the bellow list is likely not complete
# Required,
# NotRequired,
# ClassVar,
# Final,
# TypeGuard,

abcCallableGenericAlias = type(abc.Callable[[],None])

type typeLike = (
	type |
	str |
	UnionType |
	_UnionGenericAlias |
	tuple[typeLike] |
	ForwardRef |
	TypeAliasType |
	TypeVar |
	_LiteralGenericAlias |
	InitVar |
	NewType |
	_CallableType |
	_TypedDictMeta |
	# pylance dosent like this even though its a type
	abcCallableGenericAlias |
	_CallableGenericAlias |
	_AnnotatedAlias |
	_SpecialGenericAlias |
	GenericAlias |
	_GenericAlias |

	# pylance dosent like this but it is within spec and runs so...
	Literal[
		Any,
		Parameter.empty,
		Self,
		callable,
		abc.Callable,
		LiteralString,
		Never,
		NoReturn
	]
)

# this is taken from the source code of typing
# its all vars that are created with _alias
_generic_alias_types: list[_SpecialGenericAlias] = [
	typing.Hashable,
	typing.Awaitable,
	typing.Coroutine,
	typing.AsyncIterable,
	typing.AsyncIterator,
	typing.Iterable,
	typing.Iterator,
	typing.Reversible,
	typing.Sized,
	typing.Container,
	typing.Collection,
	typing.AbstractSet,
	typing.MutableSet,
	typing.Mapping,
	typing.MutableMapping,
	typing.Sequence,
	typing.MutableSequence,
	typing.ByteString,
	typing.Tuple,
	typing.List,
	typing.Deque,
	typing.Set,
	typing.FrozenSet,
	typing.MappingView,
	typing.KeysView,
	typing.ItemsView,
	typing.ValuesView,
	typing.ContextManager,
	typing.AsyncContextManager,
	typing.Dict,
	typing.DefaultDict,
	typing.OrderedDict,
	typing.Counter,
	typing.ChainMap,
	typing.Generator,
	typing.AsyncGenerator,
	typing.Type,
	# these are all defined in the same place except the two below
	typing.Pattern,
	typing.Match,
]
_alias_base_types = [typing.get_origin(t) for t in _generic_alias_types]

def are_type_compatible(
	val: Any,
	t: typeLike,
	ctx: Optional[Any] = None,
	ns: Optional[dict[str, Any]] = None
):
	# if there is no ns create one from the locals and globals
	if ns == None:
		last_frame = inspect.currentframe().f_back
		ns = last_frame.f_globals | last_frame.f_locals

	# empty is untyped so everything is type compatible
	if t == Parameter.empty: return True
	
	# if t is a protocol. this must happen before type(t) == type as these are types
	# this check is taken from runtime_checkable to check if a type is a protocol
	if type(t) == type and (issubclass(t, Generic) or getattr(t, '_is_protocol', False)):
		# dont do a isinstance check as they are slow dont always work so we need a
		# custom implimnetation anyway and they dont check signatures or types
		assert False, "TODO: protocols are still unimplimented"


	# if isinstance works on t use it note that this dosent include unions as they only
	# work if all there members work on isinstance
	if type(t) == type:return isinstance(val, t)

	# if type is Any anything is type compatible
	if t in [Any]: return True

	# if type is Never or NoReturn this value should not exist so its not compatible
	if t in [Never, NoReturn]: return False

	# resolve unresolved types
	if type(t) == str:
		# this is not a public api but this is how `typing.get_type_hints` uses it
		t = ForwardRef(t, is_argument=True, is_class=False,)
		return are_type_compatible(val, t, ctx, ns)

	# if t is a union treat as a tuple of its args
	if type(t) == UnionType or type(t) == _UnionGenericAlias:
		return are_type_compatible(val, t.__args__, ctx, ns)

	# if t is a tuple return true if any of the types are type compatible
	if type(t) == tuple: return any(are_type_compatible(val, t, ctx, ns) for t in t)

	# this means it used to be a str. resolve it
	if type(t) == ForwardRef:
		# this is also not a public api
		t = t._evaluate(ns, ns, frozenset())
		return are_type_compatible(val, t, ctx, ns)

	# resolve aliases
	if type(t) == TypeAliasType: return are_type_compatible(val, t.__value__, ctx, ns)

	# resolve None to NoneType
	if t == None: return are_type_compatible(val, NoneType, ctx, ns)

	# resolve generics
	if type(t) == TypeVar:
		# we should try to resolve but there are no decent apis

		# getting the class from just the method is using code found in
		# https://stackoverflow.com/a/25959545/15755351 as it is (relativly) easy
		# and also we can just fall back on treating like Any if this fails
		# (especialy given most generic code is not typed well enough for the next
		# step anyway)

		# if the typevar has constraints the val must be one of those types
		# however if the constraints are empty then it can be any type
		if len(t.__constraints__) > 0 and not are_type_compatible(val, t.__constraints__, ctx, ns):return False

		# if this is a function generic there is no way of telling the resolved type so treat as Any
		if hasattr(ctx, "__type_params__") and t in ctx_cls.__type_params__: return True

		# if the ctx is not a method we cant find its generic so treat as Any
		if not inspect.ismethod(ctx): return True
		# at this point the type is probably on the ctxs class
		ctx_self = ctx.__self__
		ctx_cls = ctx_self.__class__
		# if the generic belongs to another class treat it as Any as we cant resolve it
		if not hasattr(ctx_cls, "__type_params__"):return True
		if t not in ctx_cls.__type_params__:return True
		if not hasattr(ctx_self, "__orig_class__"):return True
		#this means the generics are typed
		i = ctx_cls.__type_params__.index(t) # this shouldnt fail as we have already checked t is in type params
		# this shouldnt fail as you can only supply all or none of the generics
		return are_type_compatible(val, typing.get_args(ctx_self.__orig_class__)[i], ctx, ns)

	# this means that the arguemnt should be of the type of the class it belongs to
	if t == Self:
		# this shares some code with TypeVar

		# if the ctx is not a method we cant find its self type so treat as Any
		if not inspect.ismethod(ctx): return True
		ctx_cls = ctx.__self__.__class__
		return isinstance(val, ctx_cls)

	# it type is litteral string we treat it as string as there no way (at least that i
	# know of) to figure out if a string is litteral
	if t == LiteralString: return are_type_compatible(val, str, ctx, ns)

	# type is e.g. Litteral["r", "rb", "w" ...]
	if type(t) == _LiteralGenericAlias: return val in t.__args__

	# if the type works with get_origin and looses no information then run it though
	# get origin and then check types
	if type(t) in [
		_AnnotatedAlias, # this means the type has metadata that is non standard
		_SpecialGenericAlias, # this is typings versions of builtins for typing e.g. typing.List
	]: return are_type_compatible(val, typing.get_origin(t), ctx, ns)

	# type is a dataclass InitVar[...]
	if type(t) == InitVar: return are_type_compatible(val, t.type, ctx, ns)
	
	# type is a NewType()
	if type(t) == NewType: return are_type_compatible(val, t.__supertype__, ctx, ns)

	# type is a Class[param]
	if type(t) in [GenericAlias, _GenericAlias]:
		origin = typing.get_origin(t)
		args = typing.get_args(t)
		# check that val is typecompatible with the not generic type
		if not are_type_compatible(val, origin, ctx, ns): return False
		# if this isnt a alias type from typing 
		if origin not in _alias_base_types:
			assert origin.__module__ not in ["types", "typing", "builtins"], "make sure that unknown aliases are not std types. if this fails we need to update things"
			return True # we dont know how to check this is a generic of the specified type so assume it is
		# check the generic
		alias_t = _generic_alias_types[_alias_base_types.index(origin)]
		# nparams == -1 means any amount of params
		if alias_t._nparams != -1 and len(args) != alias_t._nparams:
			# this means the user has passed in the incorect amount of generic args
			# assume they know what they are doing and return True
			# still print a warning though
			print(f"Warning: incorect parameter count passed to {t} expected {alias_t._nparams} but got {len(args)}. Did you mean to pass in a Union?", file=sys.stderr)
			return True
		# not acctualy a generic type (this probably shouldnt ever be reached)
		if alias_t._nparams == 0: return True
		if alias_t._nparams == 1: arg = args[0]
		
		# these have nparams = 0 so cant be instansiated
		# typing.Hashable,
		# typing.Sized,
		# typing.ByteString,

		match alias_t:
			# with these we dont want to accidently force new values so just assume its correct
			case typing.Iterator | typing.Generator | typing.AsyncIterator: return True
			# these types it is hard to check generis so assume they are correct
			case (
				typing.Container | typing.AsyncIterable | typing.Awaitable |
				typing.ContextManager | typing.AsyncContextManager |
				typing.AsyncGenerator
			): return True
			case typing.Tuple: return (
				len(val) == len(args) and 
				all(are_type_compatible(val, t, ctx, ns) for val, t in zip(val, args))
			)
			case (
				typing.List | typing.Deque | typing.Set | typing.FrozenSet |
				typing.MappingView | typing.KeysView | typing.ValuesView |
				typing.Iterable | typing.Reversible | typing.MutableSet |
				typing.AbstractSet | typing.Sequence |typing.MutableSequence |
				typing.Counter
			): return all(are_type_compatible(val, arg, ctx, ns) for val in val)
			case typing.ItemsView:return all(
				are_type_compatible(val[0], args[0], ctx, ns) and
				are_type_compatible(val[1], args[1], ctx, ns)
				for val in val
			)
			case (
				typing.Dict | typing.DefaultDict | typing.OrderedDict |
				typing.Collection | typing.Mapping | typing.MutableMapping |
				typing.ChainMap
			):return all(
				are_type_compatible(key, args[0], ctx, ns) and
				are_type_compatible(val[key], args[1], ctx, ns)
				for key in val
			)
			case typing.Type: return issubclass(val, arg)
			case typing.Pattern: return are_type_compatible(val.pattern, arg, ctx, ns)
			case typing.Match: return are_type_compatible(val.string, arg, ctx, ns)
		assert False, "this means that there is a missing Generic Alias"

	# this is an argumentless callable type i.e. callable or Callable
	if type(t) == _CallableType or t in [abc.Callable, callable]:
		return isinstance(val, FunctionType|BuiltinFunctionType) or hasattr(val, "__call__")

	# this is a callable type with arguments
	if type(t) in [abcCallableGenericAlias, _CallableGenericAlias]:
		if not (
			isinstance(val, FunctionType|BuiltinFunctionType) or
			hasattr(val, "__call__")
		): return False
		# this requires some more advanced type checking including ParamSpec and Concatenate
		assert False, "TODO: check that the passed in function matches the type"

	# if t is  TypedDict('name', {'x': int, ...}) or a subclass of TypedDict
	if type(t) == _TypedDictMeta: return isinstance(val, dict) and all(
		k in val and are_type_compatible(val[k], t)
		for k, t in t.__annotations__.items()
	)


	# these are the types that need special handling that are stil todo
	if (
		# Protocol - this has a stub at the top of the file
		type(t) == typing._ConcatenateGenericAlias or # Concatenate
		type(t) == typing.ParamSpec or # ParamSpec
		type(t) == typing.TypeVarTuple or # TypeVarTuple
		type(t) == typing._UnpackGenericAlias or # Unpack
		type(t) == typing.NamedTuple # NamedTuple
	): assert False, f"TODO: the type {t} has not yet been handled but is planned"

	raise TypeError(f"cannot validate type {t} if you think it should work have a go at implimenting it and create a PR")

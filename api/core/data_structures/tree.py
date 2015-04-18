from collections import MutableMapping, OrderedDict
import logging
import unittest
from api.core.data_structures.timestamp import Timestamped, getEpochMs

__author__ = 'Michael Pryor'

logger = logging.getLogger(__name__)

class SpecialDict(dict):
    def __init__(self, *args, **kwargs):
        super(SpecialDict, self).__init__(*args, **kwargs)
        self.dictionaryDepthInTree = None

def wrapDict(dic):
    specialDic = SpecialDict()
    try:
        iter(dic)
        for key, value in dic.iteritems():
            specialDic[key] = wrapDict(value)

        return specialDic
    except (TypeError, AttributeError):
        pass

    return dic


class DictTree(object):
    """ Please remember there is a good reason why dictionary is not a parameter to the constructor.
        This is so that you can pass in branches, instead of always having to refer to the root. """

    def __init__(self):
        super(DictTree, self).__init__()

    def get(self, dictionary, fullPath, functionListDepth=None, safe=None, buildBranches=None, buildBranchFunc=None):
        return self._get(dictionary, fullPath, functionListDepth, None, safe, buildBranches, buildBranchFunc)

    def _get(self, dictionary, fullPath, functionListDepth=None, treeDepth=None, safe=None, buildBranches=None, buildBranchFunc=None):
        """ @param dictionary               Dictionary to traverse.
            @param fullPath                 Iterable list of keys.
            @param functionListDepth        Depth to begin searching, starting at 0. Default is 0.
            @param treeDepth                Depth within tree, not always = to functionListDepth. Defaults to = functionListDepth.
                                            This is only used for the recursive call.
            @param safe                     If true no exceptions are raised, None is returned instead. Default is true.
            @param buildBranches            If true and part of the path doesn't exist then it is added automatically.
                                            In that event, the method will return a dictionary. Default is False.
            @param buildBranchFunc          Function to be be called to construct a branch of the tree, if None reverts to
                                            default function: lambda depth: dict().

                                            The depth parameter is the absolute position within the top level tree.
                                            Even if a sub tree is passed to this get method (not the top level tree),
                                            the depth will still be relative to the top level tree.
            @return None or item found at end of fullPath. """

        if functionListDepth is None:
            functionListDepth = 0

        if safe is None:
            safe = True

        if buildBranches is None:
            buildBranches = False

        if buildBranchFunc is None:
            buildBranchFunc = lambda depth: SpecialDict()

        # Note: this code block will fail if a dict() or other literal object is used.
        # You must use an object instead, see SpecialDict().
        #
        # Failure will mean that buildBranchFunc receives None instead of a valid depth.
        # If you are not concerned with this then you can ignore this warning.
        if treeDepth is None:
            # Retrieve from dictionary attribute.
            try:
                treeDepth = dictionary.dictionaryDepthInTree
            except AttributeError:
                pass

            try:
                # Default to function list depth.
                if treeDepth is None:
                    dictionary.dictionaryDepthInTree = functionListDepth
                    treeDepth = dictionary.dictionaryDepthInTree
            except AttributeError:
                pass
        else:
            # Store as attribute to dictionary object for later use.
            #
            # This is in case we directly access a tree branch, rather than going
            # from the root of the tree.
            try:
                dictionary.dictionaryDepthInTree = treeDepth
            except AttributeError:
                pass

        # I kept accidentally passing in strings instead of a list of strings,
        # if you have a good reason to pass in a string you can delete this without fear.
        assert not isinstance(fullPath, basestring)

        def onError(isError, str):
            if isError:
                if safe:
                    return None
                else:
                    raise KeyError(str)
            else:
                return True

        def getter(key):
            try:
                if buildBranches:
                    item = dictionary.get(key, None)

                    if not isinstance(item, MutableMapping):
                        item = buildBranchFunc(treeDepth)
                        dictionary[key] = item
                    return item
                elif safe:
                    return dictionary.get(key, None)
                else:
                    return dictionary[key]
            except AttributeError:
                return onError(True, 'Attempted to traverse leaf node')

        assert dictionary is not None
        assert fullPath is not None

        path = fullPath[functionListDepth:]
        if not onError((len(path) < 1), 'Path too long, cannot traverse below bottom of tree'):
            # note: in construction mode there is no way to recover from this since we don't know
            # what we need to construct in order to reach that depth.
            return None

        first = path[0]
        if len(path) > 1:
            dictionary = getter(first)
            if dictionary is None:
                return None

            return self._get(dictionary, fullPath, functionListDepth + 1, treeDepth + 1, safe, buildBranches, buildBranchFunc)
        else:
            return getter(first)

    def add(self, dictionary, value, fullPath, depth=None, buildBranchFunc=None):
        if depth is None:
            depth = 0

        func = lambda: value
        self.applyFunction(dictionary, func, fullPath, depth, safe=False, buildBranches=True, buildBranchFunc=buildBranchFunc)

    def applyFunction(self, dictionary, function, fullPath, depth=None, safe=None, buildBranches=None, buildBranchFunc=None):
        assert fullPath is not None
        assert dictionary is not None

        if depth is None:
            depth = 0

        if safe is None:
            safe = True

        if buildBranches is None:
            buildBranches = False

        firstPath = fullPath[:-1]
        last = fullPath[-1:][0]
        pathSize = len(fullPath) - depth

        assert pathSize > 0

        if pathSize > 1:
            dictionary = self.get(dictionary, firstPath, depth, safe, buildBranches, buildBranchFunc)

        if dictionary is None:
            if safe:
                return None
            else:
                raise KeyError('Path leads to None or cannot be followed completely: %s' % firstPath)

        try:
            newValue = function()
            dictionary[last] = newValue
        except TypeError:
            value = dictionary.get(last, None)
            newValue = function(value)
            dictionary[last] = newValue
        return newValue

    def copy(self, dictionary, depth=0, buildBranchFunc=None):
        """ Copies the tree and its branches, but not the data in the leaves. """

        if buildBranchFunc is None:
            buildBranchFunc = lambda depth: SpecialDict()

        try:
            it = iter(dictionary)
            dicCopy = buildBranchFunc(depth)
            for item in it:
                dicCopy[item] = self.copy(dictionary[item], depth + 1, buildBranchFunc)

            return dicCopy
        except TypeError:
            return dictionary




class DictTreeFunctioned(DictTree):
    """ Provides methods to manipulate a python dictionary into acting as a tree structure (a dict of dicts).

        Function lists are used, each function is applied to a different level within the tree. The order
        of the functions in the list is important. e.g. [funcA, funcB, funcC], funcA will be applied at depth 0
        to that level of the tree, funcB will be applied to depth 1 and so on.

        The add method will create dictionaries as necessary in order to grow the tree. """


    def __init__(self, hashFuncList=None, funcGetValue=None):
        """ @param hashFuncList list of functions taking a value as an argument and
            returning a hashable object or hash value.
            @param funcGetValue (optional) function to extract the value that should be stored from
            the input value. By default will store input value as is. """
        super(DictTreeFunctioned, self).__init__()

        if funcGetValue is None:
            funcGetValue = lambda x: x

        self.hash_func_list = hashFuncList
        self.func_get_value = funcGetValue

    @staticmethod
    def extractFunction(funcParameter):
        """ @param funcParameter either a stand alone value, or a tuple (value, iterableBoolean).
            If stand alone we assume to mean (value, False). This allows us to convert our
            input hash function list into a more usable form.
            @return (value, iterableBoolean). """
        try:
            iter(funcParameter)
            return funcParameter
        except TypeError:
            return funcParameter, False

    @staticmethod
    def extractKeyLists(funcArgs, value, prereqKey=None):
        if prereqKey is None:
            prereqKey = []

        if len(funcArgs) < 1:
            return [prereqKey]

        thisFuncArg = funcArgs[0]
        nextFuncArgs = funcArgs[1:]

        thisFunc, isThisFuncValueIterable = DictTreeFunctioned.extractFunction(thisFuncArg)
        thisFuncResult = thisFunc(value)

        result = []
        if isThisFuncValueIterable:
            for thisFuncSubResult in thisFuncResult:
                result += DictTreeFunctioned.extractKeyLists(nextFuncArgs, value, prereqKey + [thisFuncSubResult])
        else:
            result += DictTreeFunctioned.extractKeyLists(nextFuncArgs, value, prereqKey + [thisFuncResult])

        return result


    def addByFunction(self, dictionary, value, hashFuncList=None, depth=None, buildBranchFunc=None):
        """ @param dictionary           Dictionary to manipulate.
            @param value                Value to add to data structure.
            @param hashFuncList         If not None this list is used, otherwise
                                        the list set during initialization is used. If both lists are None
                                        this call will fail. This parameter allows for multiple object types
                                        to be added.

                                        Each hash function can be either:
                                        - function
                                        - (function, isIterableBoolean) <- tuple

                                        In the second type, the result of the function will be iterated over if isIterableBoolean
                                        is true. Each one will be treated as a unique key. Example: results from the hash functions
                                        of 0, 5, [6,7], 8, 9 will result in the value being inserted at [0, 5, 6, 8, 9] and [0, 5, 7, 8, 9]

                                        The first type is equivalent to the second in form (function, False).

            @param depth                Depth to add item in tree, starting at 0. Default is 0.
            @param buildBranchFunc      Function to be be called to construct a branch of the tree, if None reverts to
                                        default function: lambda: dict()."""
        if hashFuncList is None:
            hashFuncList = self.hash_func_list

        keyList = self.extractKeyLists(hashFuncList, value)
        value = self.func_get_value(value)

        for key in keyList:
            super(DictTreeFunctioned, self).add(dictionary, value, key, depth, buildBranchFunc)

    def getOriginalByFunction(self, dictionary, value, hashFuncList=None, depth=None):
        if hashFuncList is None:
            hashFuncList = self.hash_func_list

        keyList = self.extractKeyLists(hashFuncList, value)

        for key in keyList:
            result = super(DictTreeFunctioned, self).get(dictionary, key, depth, buildBranches=False, safe=True)
            if result is not None:
                return result

    def inByFunction(self, dictionary, value, hashFuncList=None, depth=None):
        return self.getOriginalByFunction(dictionary, value, hashFuncList, depth) is not None


class Tree(dict):
    def __init__(self, *args, **kwargs):
        super(Tree, self).__init__(*args, **kwargs)

        # Instead of using a normal argument we do it like this so that
        # this object can be instantiated in the same way as a dictionary.
        self.dict_controller = None
        self.build_branch_func = None

    def getFromTree(self, fullPath, depth=None, safe=None, buildBranches=None):
        return self.dict_controller.get(self, fullPath, depth, safe, buildBranches, self.build_branch_func)

    def addToTree(self, value, fullPath, depth=None):
        return self.dict_controller.add(self, value, fullPath, depth, self.build_branch_func)

    def applyFunctionInTree(self, function, fullPath, depth=None, safe=None, buildBranches=None):
        return self.dict_controller.applyFunction(self, function, fullPath, depth, safe, buildBranches, self.build_branch_func)

    def copyTree(self):
        tree = Tree(self.dict_controller.copy(self, self.build_branch_func))
        tree.dict_controller = self.dict_controller
        tree.build_branch_func = self.build_branch_func
        return tree

    @classmethod
    def make(cls, *args, **kwargs):
        tree = cls(*args, **kwargs)
        tree.dict_controller = DictTree()

        return tree

    @classmethod
    def makeCustom(cls, buildBranchFunc):
        tree = cls()
        tree.dict_controller = DictTree()
        tree.build_branch_func = buildBranchFunc
        return tree

class TreeFunctioned(Tree):
    def __init__(self, hashFuncList=None, funcGetValue=None, buildBranchFunc=None, *args, **kwargs):
        super(TreeFunctioned, self).__init__(*args, **kwargs)
        self.dict_controller = DictTreeFunctioned(hashFuncList=hashFuncList, funcGetValue=funcGetValue)
        self.build_branch_func = buildBranchFunc

    def addToTreeByFunction(self, value, hashFuncList=None, depth=0):
        return self.dict_controller.addByFunction(self, value, hashFuncList, depth, self.build_branch_func)

    def getOriginalByFunction(self, value, hashFuncList=None, depth=0):
        return self.dict_controller.getOriginalByFunction(self, value, hashFuncList, depth)

    def inByFunction(self, value, hashFuncList=None, depth=0):
        return self.dict_controller.inByFunction(self, value, hashFuncList, depth)

class testTree(unittest.TestCase):
    class TestObj(Timestamped):
        def __init__(self, x, y, age=None, hash=1):
            Timestamped.__init__(self)

            self.x = x
            self.y = y
            self.hash = hash

            if age is not None:
                self.timestamp = getEpochMs() - age

        def __hash__(self):
            return self.hash

        def __eq__(self, other):
            return hash(self) == hash(other)

    def testTreeFunctioned(self):
        funcList = [lambda a: a.x, lambda a: a.y]

        ob1 = testTree.TestObj(0, 50, 0)
        ob2 = testTree.TestObj(100, 150, 1000)
        ob3 = testTree.TestObj(100, 250, 2000)
        ob4 = testTree.TestObj(100, 250, 3000)
        comparisonObj = testTree.TestObj(100, 150, 1000)

        treeController = DictTreeFunctioned(hashFuncList=funcList)
        dic = SpecialDict()

        treeController.addByFunction(dic, ob1)
        treeController.addByFunction(dic, ob2)
        treeController.addByFunction(dic, ob3)
        treeController.addByFunction(dic, ob4)

        result = treeController.getOriginalByFunction(dic,comparisonObj)
        assert result is ob2

        # We override the first hash function, it will look
        # only at the second hash function.
        ob5 = testTree.TestObj(100, 300, 4000)
        treeController.addByFunction(dic[0], ob5, depth=1)

        assert dic[0][50] is ob1
        assert len(dic[0]) == 2
        assert len(dic[100]) == 2
        assert len(dic) == 2
        assert dic[100][150] is ob2
        assert dic[100][250] is ob4
        assert dic[100][250] is ob4
        assert dic[0][300] is ob5

        Timestamped.prune(dic, 2100)

        assert len(dic) == 2
        assert len(dic[0]) == 1
        assert len(dic[100]) == 1
        assert dic[0][50] is not None
        assert dic[100][150] is not None

    def testDictTree(self):
        dic = SpecialDict()
        dic.update(wrapDict({'hello': {'sub 1': {'sub 2': 'world', 'another thing on sub 2': 'universe'}}, 'what': 'is the time?'}))

        tree = DictTree()
        assert tree.get(dic, ['hello', 'sub 1', 'another thing on sub 2']) == 'universe'
        assert tree.get(dic, ['hello', 'sub 1', 'sub 2']) == 'world'
        assert tree.get(dic, ['hello2', 'sub 1', 'sub 2']) is None
        assert tree.get(dic, ['hello', 'subbb 1', 'sub 2']) is None
        assert tree.get(dic, ['hello', 'sub 1', 'sub 2', 'sub 3', 'sub 4']) is None

        tree.add(dic, 'I added this!', ['hello', 'sub 1', 'sub 2', 'world', 'problem'])
        assert tree.get(dic, ['hello', 'sub 1', 'sub 2', 'world', 'problem']) == 'I added this!'

        tree.add(dic, 'This is all new!', ['this', 'is', 'all', 'new'])
        assert tree.get(dic, ['this', 'is', 'all', 'new']) == 'This is all new!'

    def testMultiKeyTreeFunctioned(self):
        funcList = [(lambda a: a.x,True), (lambda a: a.y,True)]

        ob1 = testTree.TestObj([0,1], [50,51])
        ob2 = testTree.TestObj([100,101], [150,151])

        treeController = DictTreeFunctioned(hashFuncList=funcList)
        dic = SpecialDict()

        treeController.addByFunction(dic, ob1)
        treeController.addByFunction(dic, ob2)

        print 'hello wait'

    def testDictTreeBranchFunc(self):
        funcList = [lambda a: a.x, lambda a: a.y, lambda a: hash(a), lambda a: a.x, lambda b: b.y]
        subFuncList = [lambda a: hash(a), lambda a: a.x, lambda b: b.y]

        ob1 = testTree.TestObj(100, 50, hash=1)
        ob2 = testTree.TestObj(100, 50, hash=100)

        treeController = DictTreeFunctioned(hashFuncList=funcList)
        dic = OrderedDict()

        buildFuncResultList = []

        def buildBranchFunc(depth):
            logger.info('Building branch from depth: %d' % depth)
            buildFuncResultList.append(depth)
            return OrderedDict()

        treeController.addByFunction(dic, ob1, buildBranchFunc=buildBranchFunc)

        # Test not adding from root.
        treeController.addByFunction(dic[100][50], ob2, hashFuncList=subFuncList, buildBranchFunc=buildBranchFunc)

        assert dic[100][50][1][100][50] is not None
        assert dic[100][50][100][100][50] is not None
        assert buildFuncResultList == [0,1,2,3,2,3]